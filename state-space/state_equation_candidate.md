# State Equation Candidate

This note is restricted to the finite observed tables listed in README.md.

## State Variable Candidate

`X_t = (band_t, R_before_t, R_after_t, boundary_front_t, chain_status_t, residue32_t, transition_k_t)`

The exported `state_table.csv` uses a composite `state_id` built from band, remaining-K face, boundary-front, chain status, transition k, and residue32.

## Observation Variables

- side label: miss/control, used as a bookkeeping label only
- trajectory id and pair id
- position in the local word window
- residue16 as a finer residue coordinate
- exit_distance as a local boundary coordinate

## Input Or Perturbation-Like Variables

The finite table can be read as a stochastic transition map:

`P(X_{t+1} = y | X_t = x)`

or as

`X_{t+1} = F(X_t, epsilon_t)`

`epsilon_t` stands for unresolved branching in the finite table, not a claim about unobserved dynamics.

## Nearly Preserved Quantities

Candidate near-preserved quantities should be read from high dominant target share and low transition entropy in `branching_table.csv`. Several states are deterministic_like within this finite sample.

## Strong Branching States

- band=64-127|R=67->62|front=near_exit_front|chain=avoid_then_caught|k=5|res32=3->30: out_degree=3, entropy=1.485475, dominant_share=0.5
- band=64-127|R=67->63|front=near_exit_front|chain=avoid_then_caught|k=4|res32=3->31: out_degree=2, entropy=1.0, dominant_share=0.5
- band=64-127|R=70->63|front=near_exit_front|chain=avoid|k=7|res32=6->31: out_degree=2, entropy=1.0, dominant_share=0.5
- band=64-127|R=67->60|front=near_exit_front|chain=avoid_then_caught|k=7|res32=3->28: out_degree=2, entropy=0.918296, dominant_share=0.666667
- band=64-127|R=64->63|front=lower_edge_front|chain=avoid_then_caught|k=1|res32=0->31: out_degree=2, entropy=0.77935, dominant_share=0.769231

## Strong Merge Targets

- band=32-63|R=32->29|front=lower_edge_front|chain=avoid_then_caught|k=3|res32=0->29: reached by 7 distinct transition rows
- band=32-63|R=33->31|front=lower_edge_front|chain=avoid_then_caught|k=2|res32=1->31: reached by 7 distinct transition rows
- band=64-127|R=64->63|front=lower_edge_front|chain=avoid_then_caught|k=1|res32=0->31: reached by 7 distinct transition rows
- band=32-63|R=32->30|front=lower_edge_front|chain=avoid_then_caught|k=2|res32=0->30: reached by 6 distinct transition rows
- band=16-31|R=18->14|front=near_exit_front|chain=avoid|k=4|res32=18->14: reached by 2 distinct transition rows

## Bundle As State Variable Or Observation Label

`B(x -> y) = { feature_i : feature_i(x) != feature_i(y) }`

For now, bundle strings are best treated as observed labels attached to transitions. Frequent bundle strings should not replace state/transition rows unless their delta patterns are also compact.

## Parts That Can Be Written Now

- a finite stochastic transition table
- source-level branching summary
- transition-attached bundle labels
- finite-sample merge target inventory

## Parts To Keep Open

- whether any bundle is compact enough to become a state variable
- whether miss/control separation remains after conditioning on state
- whether residue16 adds necessary resolution beyond residue32
- whether exit_distance should be in X_t or treated as an observed boundary coordinate

## Bundle Stability Snapshot

- stable_candidate bundles: 0
- frequent_but_diverse bundles: 3
- frequent and stable are kept separate in the exported table.
