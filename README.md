# Review Classifier: Baseline V0

## Scope of This Run

This run uses only the fixed set of 81 Dev reviews for a policy-only baseline. The 21 Test reviews are not included in this folder.
No few-shot examples are added, the policy is not rewritten based on human labels, and no second round of optimization is performed.
The policy is the complete version you provided; only punctuation and formatting have been standardized.
Each API call is independent. No previous review or model response is included in the next request.

## Running on Windows / VS Code / Anaconda

1. Extract the entire folder. Do not copy only `classifier.py`.
2. Open a terminal in this folder, or navigate to this directory.
3. Run:

```powershell
python classifier.py --dry-run
python classifier.py
```

When prompted, enter the provider, model ID, and API key. Choose `openai`, `anthropic`, or `compatible` as the provider.
Enter an API model ID available to your account, not the model's display name shown on a website.
The API key is entered as hidden input and is not saved. Do not share it in chats, spreadsheets, or shared files.
For compatible providers, enter the full HTTPS Chat Completions endpoint URL.
Python 3.10 or later is required. No pip installation or GPU is needed.

Note: The code runs on your computer, but reviews are sent to the cloud API you select. The API account must have available credits; processing 81 reviews will incur API charges.

## Running in Jupyter

Place the notebook in the extracted folder and run the following cells. Enter the API key when prompted in the cell output.

```python
%run classifier.py --dry-run
%run classifier.py
```

Optional: Test the connection with one Dev review first, then continue with the same run:

```powershell
python classifier.py --provider anthropic --model YOUR_MODEL_ID --limit 1
python classifier.py --provider anthropic --model YOUR_MODEL_ID
```

Do not modify the prompt based on the first result and continue using the same run. The script checks the prompt, data, model, and parameters to prevent mixing versions.
By default, the script does not explicitly set `temperature`; it uses the service default and records it as `null`. If supported by the model, you can set it to 0 with `--temperature 0`, but do not change it during a run.
Use a different `--run` name for each prompt version, for example `--run v1`. Do not create an improved version before this run is complete.

## Outputs and Team Collaboration

The first run creates `runs/baseline_v0/`:

- `dev_results.csv`: The 81 reviews' original human labels, model predictions, rationales, and TP/FP/FN/TN classifications.
- `errors_for_team.csv`: Misclassifications and incomplete items, along with analysis columns for teammates to fill in.
- `metrics.json`: Precision, recall, F1, accuracy, and coverage for overall, clear, and edge-case reviews.
- `evaluation.md`: Confusion matrix and results overview.
- `run_config.json`, `prompt_used.txt`: Experiment configuration and the complete prompt used.
- `raw_responses.jsonl`: Each raw API response, for review, usage tracking, and resuming an interrupted run. It does not contain the API key.

Share these files with teammates: `dev_results.csv`, `errors_for_team.csv`, `evaluation.md`, `prompt_used.txt`, and `run_config.json`.
Teammates can document the reasons for misclassifications, policy or model issues, and improvement suggestions. Then decide together whether to create V1.
CSV files can be opened in Excel. If you save them in another format, keep the original CSV files as the record for this run.

## Evaluation Rules

Positive = Violation. TP means a violation was correctly identified; FP means a non-violation was incorrectly flagged; FN means a violation was missed; TN means a non-violation was correctly allowed.
Precision = TP/(TP+FP), Recall = TP/(TP+FN), and F1 = 2TP/(2TP+FP+FN). If a denominator is zero, the value is saved as `null` rather than being presented as 0 or 1.
Failed requests, invalid JSON, and invalid labels are all retained as Unscored; they are not changed to Non-violation.
When there are Unscored items, the metrics reflect only the successfully classified subset. Resolve the failures before comparing versions.
If a run is interrupted, rerun the same command: successful items are skipped and failed items are retried. Progress is saved after each response.
The dataset contains 36 Violation labels and 45 Non-violation labels; 17 reviews are Edge cases.
These results should be described as Dev results only, not as held-out test performance.

## Data Sources and Limitations

`dev.csv` was extracted from the Dev worksheet in the pre-split dataset. IDs, original row numbers, reviews, sources, final labels, and difficulty ratings are preserved as provided.
The model receives only the policy and review fields. Annotations, difficulty ratings, sources, IDs, and discussion notes are not sent to the model.
No images, purchase dates, or cross-account behavior data are provided. Policy items that depend on this evidence may not be assessable in this text-only classification task and should be discussed in the error analysis.

## API Documentation

- https://platform.openai.com/docs/api-reference/chat/create
- https://platform.claude.com/docs/en/api/messages/create

When using a compatible service, also check its official API documentation. Errors caused by API or model limitations require configuration changes and a retry; they must not be treated as classification results.
