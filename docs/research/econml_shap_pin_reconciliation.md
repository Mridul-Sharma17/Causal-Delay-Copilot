# EconML and SHAP pin reconciliation for hosted Core

Research date: 2026-08-04
Wayfinder ticket: [Reconcile the EconML and SHAP pin contract for hosted Core](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/70)
Map: [Plan the Round 2 hosted delivery of Causal Delay Copilot](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/66)

## Decision

Authorize one pin-only amendment:

```text
Keep:   EconML==0.16.0
Change: SHAP==0.49.1 -> SHAP==0.48.0
Keep:   every other authoritative runtime pin unchanged
Host:   CPython 3.12.13 on x86_64 Linux with glibc >= 2.28
```

This is the narrowest published, supported reconciliation. EconML 0.16.0 is still the latest published EconML release, declares Python 3.12 and Linux support, and requires `shap>=0.38.1,<0.49.0`; SHAP 0.48.0 is the highest final SHAP release inside that interval ([EconML release history and files](https://pypi.org/project/econml/), [EconML 0.16.0 dependency declaration](https://github.com/py-why/EconML/blob/v0.16.0/pyproject.toml#L19-L29), [SHAP release history](https://pypi.org/project/shap/)). Keeping SHAP 0.49.1 by ignoring dependency metadata is unsupported. Upgrading EconML is not a published-release option, and using an unreleased branch would replace an exact release pin with a mutable source dependency.

The required Context7 library lookup resolved EconML to the high-reputation official ID `/py-why/econml`. The subsequent Context7 documentation request was blocked by the environment approval reviewer before it executed, so no Context7 excerpt is treated as evidence. The findings instead cite versioned upstream source, official project documentation, and PyPI publisher metadata directly.

The amendment does not add `CausalForestDML` to Core. The authoritative engine contract says Core neither fits nor displays it and only keeps EconML installed for the wider researched stack ([Core scope resolution](../specs/executable-causal-engine-contract.md#scope-resolution-for-heterogeneous-effects), [runtime-pin boundary](../specs/executable-causal-engine-contract.md#runtime-pins)). The predictive contract does execute SHAP: it requires a fresh seeded `PermutationExplainer` over calibrated `predict_proba(X)[:, 1]`, an identity link, `max_evals = 10 * (2 * p + 1)`, and reconstruction residual at most `1e-6` ([Predictive Attribution contract](../specs/risk-signal-pre-award-predictive-baseline-contract.md#predictive-attribution)). SHAP 0.48.0 exposes the required model-agnostic permutation algorithm and seeded constructor, and documents local accuracy through forward/reverse permutations ([versioned implementation](https://github.com/shap/shap/blob/v0.48.0/shap/explainers/_permutation.py), [official API](https://shap.readthedocs.io/en/stable/generated/shap.PermutationExplainer.html)).

## Evidence

### Package and lock resolution

A disposable uv project used the complete authoritative scientific pin set, changing only SHAP to 0.48.0:

```text
CPython==3.12.13
DoubleML==0.11.3
EconML==0.16.0
DoWhy==0.14
scikit-learn==1.6.1
NumPy==2.2.6
SciPy==1.15.3
Statsmodels==0.14.6
pandas==2.3.3
PyArrow==23.0.1
joblib==1.5.3
threadpoolctl==3.6.0
SHAP==0.48.0
```

The direct pins above come from the live Core specification; the local engine and predictive contracts confirm the scientific and SHAP behavior boundaries ([Core specification](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/18), [engine runtime pins](../specs/executable-causal-engine-contract.md#runtime-pins), [predictive model discipline](../specs/risk-signal-pre-award-predictive-baseline-contract.md#model-discipline)).

Commands and observed results:

```powershell
uv lock --python 3.12.13
# Resolved 70 packages; wrote uv.lock.

uv lock --check
# PASS: lock was current and unchanged.

uv sync --locked --python 3.12.13 --no-build
# PASS on Windows: installed 69 wheel packages; no source builds.
```

The temporary project declared:

```toml
[tool.uv]
package = false
required-environments = [
  "sys_platform == 'linux' and platform_machine == 'x86_64'",
]
```

`required-environments` makes uv require the locked resolution to cover the named platform; `--locked` refuses to update a stale lock ([uv required environments](https://docs.astral.sh/uv/concepts/resolution/#required-environments), [uv locked sync behavior](https://docs.astral.sh/uv/concepts/projects/sync/)). A stronger foreign-target check then forced every selected Linux distribution to be a wheel:

```powershell
uv export --locked --format requirements-txt --no-emit-project `
  --no-hashes --output-file linux-requirements.txt

uv pip install --target linux-site --python-version 3.12.13 `
  --python-platform x86_64-manylinux_2_28 --only-binary :all: `
  --requirements linux-requirements.txt
# PASS: resolved and installed 68 Linux wheel packages; no source builds.
```

The same wheel-only command deliberately targeted at `x86_64-manylinux2014` (glibc 2.17) failed because `contourpy==1.3.3` had no usable wheel. The supported hosting baseline must therefore be glibc 2.28 or newer, not generic old Linux. The `manylinux_2_28` tag denotes wheels built for glibc 2.28 and later ([PyPA manylinux specification](https://github.com/pypa/manylinux#manylinux_2_28-almalinux-8-based)).

The existing hosting note correctly identified the old pins as unsatisfiable; this research replaces only that open compatibility fact and does not select a host ([Round 2 hosting path](round2_hosting_path.md#dependency-and-footprint-verification)).

### Focused behavior checks

The checks ran in the disposable locked environment under actual CPython 3.12.13 on Windows 11. They imported every exact direct package version listed above and exercised the two disputed behaviors.

```powershell
uv run --locked --no-sync regression_check.py
# PASS
```

`CausalForestDML` check:

- fit the unchanged EconML 0.16.0 class twice on a deterministic binary-treatment synthetic fixture;
- fixed nuisance models, seeds, folds, one job, 40 forest estimators, and disabled inference;
- both `effect(X[:8])` results had shape `(8,)`, were finite, and had maximum repeat delta `0.0`.

This is an import/API/determinism guard for the installed Stretch dependency, not evidence that CausalForest is now part of Core or that a particular causal estimate is scientifically validated. EconML's official 0.16.0 example defines the same `fit(Y, T, X=X, W=W)` then `effect(X_test)` behavior ([EconML 0.16.0 project documentation](https://pypi.org/project/econml/0.16.0/)). Keeping EconML at exactly 0.16.0 avoids a method-version change.

`PermutationExplainer` check:

- trained the pinned scikit-learn 1.6.1 `HistGradientBoostingClassifier`, froze it, and sigmoid-calibrated it on a disjoint cohort;
- explained `calibrated.predict_proba(X)[:, 1]` with a frozen 20-row background, identity link, and a fresh explainer with seed `0`;
- for `p = 4`, used the contract value `max_evals = 10 * (2 * p + 1) = 90`;
- score `0.7053012934604204` reconstructed as `0.7053012934604206`;
- absolute additivity residual was `2.220446049250313e-16`, well below `1e-6`;
- a second fresh explainer produced maximum contribution delta `0.0`.

This directly exercises the locked predictive path rather than EconML's unrelated `shap_values()` convenience method. SHAP's official documentation describes `PermutationExplainer` as model-agnostic, seeded, and locally accurate through complete forward/reverse permutations ([SHAP PermutationExplainer API](https://shap.readthedocs.io/en/stable/generated/shap.PermutationExplainer.html)).

## Inference and residual risk

The evidence is strong enough to amend the version contract because the only direct version change is to the package whose locked behavior was exercised, the EconML class version is unchanged, the full graph resolves to a `uv.lock`, and a wheel-only Linux x86_64/glibc 2.28 target succeeds.

It is **not** an actual Linux execution result. Docker was unavailable and no usable WSL distribution was present, so native imports, C-extension loading, and the two regressions ran on Windows. Foreign-target installation proves distribution availability and resolver compatibility, not runtime behavior inside the final container. Before selecting Railway or declaring the hosted build ready, the bounded deployment prototype must still run all of the following inside the exact Linux image:

1. `uv sync --locked --no-build` from a clean cache;
2. the same direct-version import assertion;
3. the `CausalForestDML` focused check, even though Core does not execute it;
4. the contract-shaped `PermutationExplainer` reconstruction/determinism check; and
5. the broader import gate already required by the hosting note.

The uv lock also resolves unpinned transitives (for example Numba, llvmlite, LightGBM, and plotting/CVXPY dependencies). The committed `uv.lock`, not a later unconstrained re-resolution, must therefore be the release authority. Any later direct-pin or lock refresh requires rerunning these checks.

## Recommended specification amendment

Amend the Core technology/pin section only after the tracker owner separately authorizes a specification edit. Recommended normative wording:

> Replace `SHAP 0.49.1` with `SHAP 0.48.0`. Retain `EconML 0.16.0` and every other scientific direct pin. The hosted CPython 3.12.13 x86_64 Linux image must provide glibc 2.28 or newer, install exclusively from the committed `uv.lock` with source builds disabled, and pass the version/import, `CausalForestDML`, and contract-shaped `PermutationExplainer` regression gates inside that image. This pin amendment does not move `CausalForestDML` into Core scope or weaken the predictive attribution contract.

No product implementation, authoritative specification, tracker issue, map, or ticket was changed during this research.
