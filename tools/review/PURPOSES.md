# What each purpose label means, and what counts as evidence

A purpose is recorded on a method when the method's own paper, README or
documentation shows the method being used for it, evaluated for it, or
explicitly intended for it. Reviewer opinion about what a method *could*
do is not evidence.

| purpose | meaning | counts as evidence |
|---|---|---|
| open_release | the synthetic output is meant to be shared or published in place of the real data | the paper or README frames the output as releasable, shareable, a public substitute, or a privacy-preserving release; a formal privacy guarantee; a generator that never reads real records |
| statistical_replication | the synthetic data should reproduce the real data's distributions and relationships closely enough to rerun an analysis on it | fidelity evaluation (marginals, correlations, statistical similarity), claims that analyses on synthetic match analyses on real |
| ml_augmentation | adding synthetic rows to train a predictive model | ML utility or train-on-synthetic-test-on-real evaluation, "augmentation" or "training data" framing |
| imbalance_correction | oversampling a rare class | explicit minority-class or class-imbalance framing or experiments |
| causal_inference | the synthetic data preserves a known or specified causal structure | DAG / structural causal model / intervention framing; simulation from known mechanisms |
| pipeline_testing | exercising software, formats or pipelines; no realism claim | testing, interoperability, format conformance, "development data" framing |
| education | teaching material, demonstrations, training courses | tutorial, course, teaching, demonstration framing |
| benchmarking | used as a baseline or as a benchmark dataset for comparing generators or metrics | the method is used as a baseline in its own or others' experiments, provides benchmark data, or its README positions it so |

Verdicts: `supported` when at least one verbatim quote from the fetched
sources shows it; `not_supported` when the sources were read and nothing
supports it; `unclear` when the sources are thin (no full text, short
README) and the question cannot be settled from them.
