# FormulAI — Project Memory & Knowledgebase

This document serves as a persistent, graph-like mapping of the current architecture and state to ensure no deprecated models, variables, or pipelines are left lingering. 

## 1. Core Architectural Truth
The predictor has successfully transitioned from a 4-Stage Binary Classification Pipeline to a 1-Stage Learning-to-Rank (LTR) + 2 Auxiliary Heads Pipeline.

### Active Models & Variables
* `_ltr_model` (Type: `F1LTRRanker`): The core LambdaMART XGBoost/LightGBM ensemble. Replaces the old `_model`, `_stage1_model`, and TabNet.
* `_dnf_head` (Type: `XGBClassifier`): Auxiliary model trained to predict mechanical/crash failures.
* `_pace_head` (Type: `XGBRegressor`): Auxiliary model trained to predict lap time advantages.

### Target Definitions
* **Old Truth**: Predict binary `is_podium` (1 or 0) using standard LogLoss.
* **New Truth**: Predict ranking `relevance` (F1 points) using `NDCG@3`. 
* **Softmax Output**: Because probabilities across the 20-driver grid MUST sum to exactly `1.0`, we push raw ranking scores through a softmax layer. This is explicitly consumed by `models_v2/stage2_live.py` and `models_v2/stage4_simulator.py`.

## 2. API Endpoint Map (`api/main.py`)
All endpoints have been rerouted to use `_ltr_model` and the `get_ensemble_predictions()` function.
* `/api/v1/predict/{year}/{round}`: (Fixed) Native LTR.
* `/api/v1/predict/{year}/{round}/live`: (Fixed) LTR prior + Bayesian live updates.
* `/api/v1/predict/{year}/{round}/simulate`: (Fixed) LTR prior + Counterfactual modifiers.
* `/api/v1/predict/{year}/{round}/monte-carlo`: (Fixed)
* `/api/v1/predict/{year}/{round}/full-race`: (Fixed) Native LTR. 
* `/api/v1/evaluation`: (Fixed) Uses `_ltr_model` for next race podium probabilities. 

## 3. Tech Debt & Potential Errors (To-Fix)
The aggressive refactoring left several "ghosts" in the system that must be purged or monitored:

- [x] **`api/main.py` (Line 972)**: Missed `_model` reference in `get_evaluation_summary()`. (Fixed - hot reloaded).
- [x] **`tests/test_api.py` (Line 17)**: The mock test `test_predict_model_not_loaded` still monkeypatches the old `_model` variable instead of `_ltr_model`. (Fixed).
- [x] **`compare_model.py` (Line 42)**: Updated to import `F1LTRRanker` and load `_ltr_model` for direct ensemble benchmarking.
- [x] **`README.md`**: Fully rewritten to reflect the new LTR architecture (`Auxiliary Heads -> LTR Ensemble -> Softmax Calibration`) and the new `deep_tune.py` workflow.
- [x] **Frontend UI (`frontend_v2`)**: Updated the Next.js UI to properly declare "powered by a Learning-to-Rank (LTR) ensemble" rather than focusing solely on the Monte Carlo backend.
- [ ] **`api/chatbot/agent.py`**: The internal LLM chatbot (if active) may still have tool calls or RAG documents referencing the old binary logic. Needs a static audit.

## 4. Next Steps
Whenever launching new agents or returning to this project, read this `memory.md` file first to rebuild context and prevent variable mismatches.
