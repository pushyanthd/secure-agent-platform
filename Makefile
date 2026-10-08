UV ?= $(shell command -v uv 2>/dev/null || echo .venv/bin/uv)
export UV_CACHE_DIR ?= $(CURDIR)/artifacts/uv-cache

.PHONY: setup check doctor demo-replay sandbox-build sandbox-smoke demo-isolated models-fetch model-serve eval-smoke
PROFILE ?= mac-small
NODE_OS := $(shell uname -s | tr A-Z a-z)
NODE_ARCH := $(shell uname -m | sed -e 's/x86_64/x64/' -e 's/aarch64/arm64/')
NODE_BIN := $(CURDIR)/artifacts/runtime/node-v24.21.0-$(NODE_OS)-$(NODE_ARCH)/bin
export PATH := $(NODE_BIN):$(PATH)
export npm_config_cache ?= $(CURDIR)/artifacts/npm-cache

.PHONY: ui-setup ui-build ui-check ui-test
ui-setup:
	cd frontend && npm ci --ignore-scripts --no-audit --no-fund

ui-build:
	cd frontend && npm run build

ui-check:
	cd frontend && npm run check

ui-test:
	cd frontend && npm test

.PHONY: package-check
PACKAGE_DIR ?= artifacts/v1-package-$(shell date +%Y%m%d-%H%M%S)
package-check: ui-build
	test ! -e "$(PACKAGE_DIR)"
	$(UV) build --out-dir "$(PACKAGE_DIR)"
	$(UV) run --locked python scripts/check_package.py --dist "$(PACKAGE_DIR)"

.PHONY: eval-suite eval-suite-live eval-tools eval-tools-isolated eval-tools-live
.PHONY: eval-multi-attack
.PHONY: eval-development eval-expansion eval-ticket-scope eval-response-scope
.PHONY: eval-receipt-pilot-control-live eval-receipt-pilot-treatment-live
.PHONY: eval-receipt-disclosure-control-live eval-receipt-disclosure-treatment-live
eval-receipt-disclosure-control-live:
	$(UV) run --locked agentguard eval-suite --live --variants defended --suite scenarios/dev/receipt-disclosure-control-v1.json --model-profile config/model-$(PROFILE).json

eval-receipt-disclosure-treatment-live:
	$(UV) run --locked agentguard eval-suite --live --variants defended --suite scenarios/dev/receipt-disclosure-treatment-v1.json --model-profile config/model-$(PROFILE).json

eval-receipt-pilot-control-live:
	$(UV) run --locked agentguard eval-suite --live --variants defended --suite scenarios/dev/receipt-live-pilot-control-v1.json --model-profile config/model-$(PROFILE).json

eval-receipt-pilot-treatment-live:
	$(UV) run --locked agentguard eval-suite --live --variants defended --suite scenarios/dev/receipt-live-pilot-treatment-v1.json --model-profile config/model-$(PROFILE).json

.PHONY: eval-effect-receipt eval-effect-receipt-control
eval-effect-receipt:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/effect-receipt-treatment-v1.json

eval-effect-receipt-control:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/effect-receipt-control-v1.json

eval-response-scope:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/response-scope-v1.json

eval-ticket-scope:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/expansion-v2.json

eval-development:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/suite-v5.json

eval-expansion:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/expansion-v1.json

eval-multi-attack:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/multi-attack-v1.json

eval-tools:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/tools-v1.json

eval-tools-isolated:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/tools-v1.json --sandbox-manifest artifacts/sandbox/manifest.json

eval-tools-live:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/tools-v1.json --live --model-profile config/model-$(PROFILE).json

.PHONY: demo-durable
.PHONY: control-smoke api-serve worker
control-smoke:
	$(UV) run --locked agentguard control-smoke

api-serve:
	$(UV) run --locked agentguard api-serve

worker:
	$(UV) run --locked agentguard worker

demo-durable:
	$(UV) run --locked agentguard demo-durable

eval-suite:
	$(UV) run --locked agentguard eval-suite

eval-suite-live:
	$(UV) run --locked agentguard eval-suite --live --model-profile config/model-$(PROFILE).json

setup:
	$(UV) sync --locked

check:
	$(UV) run --locked ruff check .
	$(UV) run --locked ruff format --check .
	$(UV) run --locked mypy src scripts/compare_receipt_pilot.py scripts/report_release.py scripts/utility_pilot.py scripts/model_pilot.py scripts/screen_model_pilot.py scripts/completion_pilot.py scripts/completion_broad.py scripts/decision_review.py scripts/decision_structured.py scripts/workflow_comparison.py scripts/resource_completion.py scripts/portfolio_check.py scripts/artifact_volume.py scripts/measure_artifact_volume.py scripts/measure_live_recovery.py scripts/candidate_release.py scripts/pc/summarize_native_network.py scripts/check_package.py
	$(UV) run --locked pytest

doctor:
	$(UV) run --locked agentguard doctor

demo-replay:
	$(UV) run --locked agentguard demo-replay

sandbox-build:
	$(UV) run --locked agentguard sandbox-build

sandbox-smoke:
	$(UV) run --locked agentguard sandbox-smoke

demo-isolated:
	$(UV) run --locked agentguard demo-replay --sandbox-manifest artifacts/sandbox/manifest.json

models-fetch:
	$(UV) run --locked agentguard models-fetch --profile config/model-$(PROFILE).json

model-serve:
	$(UV) run --locked agentguard model-serve --profile config/model-$(PROFILE).json

eval-smoke:
	$(UV) run --locked agentguard eval-smoke --profile config/model-$(PROFILE).json

.PHONY: eval-receipt-broad eval-receipt-broad-live release-check
# Six known development tasks × five inputs × two profiles; never held-out evidence.
eval-receipt-broad:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/receipt-broad-v1.json --variants baseline,defended

eval-receipt-broad-live:
	$(UV) run --locked agentguard eval-suite --suite scenarios/dev/receipt-broad-v1.json --variants baseline,defended --live --model-profile config/model-$(PROFILE).json

release-check:
	$(UV) run --locked agentguard release-check --output artifacts/release-checks-$(shell date +%Y%m%d-%H%M%S)

.PHONY: release-validate release-prepare release-plan release-start release-status release-report
RELEASE_DIR ?= artifacts/frozen-release-v1
RELEASE_SESSION ?= artifacts/release-session
# Blank EPISODES finishes the remaining schedule; EPISODES=10 bounds this session.
EPISODES ?=
release-validate:
	$(UV) run --locked agentguard release-validate

release-prepare:
	$(UV) run --locked agentguard release-prepare --output $(RELEASE_DIR) --model-profile config/model-$(PROFILE).json

release-plan:
	$(UV) run --locked agentguard release-launch --freeze $(RELEASE_DIR)/freeze.json --session $(RELEASE_SESSION) --plan-only --model-profile config/model-$(PROFILE).json

release-start:
	$(UV) run --locked agentguard release-launch --freeze $(RELEASE_DIR)/freeze.json --session $(RELEASE_SESSION) $(if $(EPISODES),--max-episodes $(EPISODES),) --model-profile config/model-$(PROFILE).json

release-status:
	$(UV) run --locked agentguard release-progress --session $(RELEASE_SESSION)

release-report:
	$(UV) run --locked python scripts/report_release.py --session "$(RELEASE_SESSION)"

.PHONY: utility-prepare utility-start utility-status utility-report utility-validate
UTILITY_SESSION ?= artifacts/utility-pilot-v1
utility-validate:
	$(UV) run --locked python scripts/build_utility_pilot.py --check
	$(UV) run --locked pytest tests/test_utility_pilot.py

utility-prepare:
	$(UV) run --locked python scripts/utility_pilot.py prepare --session "$(UTILITY_SESSION)" --model-profile config/model-$(PROFILE).json

utility-start:
	$(UV) run --locked python scripts/utility_pilot.py run --session "$(UTILITY_SESSION)" $(if $(EPISODES),--max-episodes $(EPISODES),)

utility-status:
	$(UV) run --locked python scripts/utility_pilot.py status --session "$(UTILITY_SESSION)"

utility-report:
	$(UV) run --locked python scripts/utility_pilot.py report --session "$(UTILITY_SESSION)"

.PHONY: model-pilot-prepare model-pilot-start model-pilot-status model-pilot-report
MODEL_PILOT_SESSION ?= artifacts/utility-model-instruct-v1
MODEL_PILOT_PROFILE ?= mac-instruct
model-pilot-prepare:
	$(UV) run --locked python scripts/model_pilot.py prepare --session "$(MODEL_PILOT_SESSION)" --model-profile config/model-$(MODEL_PILOT_PROFILE).json

model-pilot-start:
	$(UV) run --locked python scripts/model_pilot.py run --session "$(MODEL_PILOT_SESSION)" $(if $(EPISODES),--max-episodes $(EPISODES),)

model-pilot-status:
	$(UV) run --locked python scripts/model_pilot.py status --session "$(MODEL_PILOT_SESSION)"

model-pilot-report:
	$(UV) run --locked python scripts/model_pilot.py report --session "$(MODEL_PILOT_SESSION)"

.PHONY: model-screen-declare model-screen-start
model-screen-declare:
	$(UV) run --locked python scripts/screen_model_pilot.py declare --session "$(MODEL_PILOT_SESSION)"

model-screen-start:
	$(UV) run --locked python scripts/screen_model_pilot.py run --session "$(MODEL_PILOT_SESSION)"

.PHONY: decision-prepare decision-start decision-status decision-report
DECISION_SESSION ?= artifacts/pc-wsl/decision-review-v1
DECISION_PROFILE ?= artifacts/pc-wsl/model-profile.json
DECISION_SANDBOX ?= artifacts/sandbox/manifest.json
decision-prepare:
	$(UV) run --locked python scripts/decision_review.py prepare --session "$(DECISION_SESSION)" --model-profile "$(DECISION_PROFILE)" --sandbox-manifest "$(DECISION_SANDBOX)"

decision-start:
	$(UV) run --locked python scripts/decision_review.py run --session "$(DECISION_SESSION)" $(if $(EPISODES),--max-episodes $(EPISODES),)

decision-status:
	$(UV) run --locked python scripts/decision_review.py status --session "$(DECISION_SESSION)"

decision-report:
	$(UV) run --locked python scripts/decision_review.py report --session "$(DECISION_SESSION)"

.PHONY: portfolio-check
portfolio-check:
	$(UV) run --locked python scripts/portfolio_check.py

.PHONY: structured-prepare structured-start structured-status structured-report
STRUCTURED_SESSION ?= artifacts/pc-wsl/decision-structured-v2
structured-prepare:
	$(UV) run --locked python scripts/decision_structured.py prepare --session "$(STRUCTURED_SESSION)" --model-profile "$(DECISION_PROFILE)" --sandbox-manifest "$(DECISION_SANDBOX)"

structured-start:
	$(UV) run --locked python scripts/decision_structured.py run --session "$(STRUCTURED_SESSION)" $(if $(EPISODES),--max-episodes $(EPISODES),)

structured-status:
	$(UV) run --locked python scripts/decision_structured.py status --session "$(STRUCTURED_SESSION)"

structured-report:
	$(UV) run --locked python scripts/decision_structured.py report --session "$(STRUCTURED_SESSION)"

.PHONY: workflows-prepare workflows-start workflows-status workflows-report
WORKFLOW_SESSION ?= artifacts/pc-wsl/workflow-comparison-v1
workflows-prepare:
	$(UV) run --locked python scripts/workflow_comparison.py prepare --session "$(WORKFLOW_SESSION)" --model-profile "$(DECISION_PROFILE)" --sandbox-manifest "$(DECISION_SANDBOX)"

workflows-start:
	$(UV) run --locked python scripts/workflow_comparison.py run --session "$(WORKFLOW_SESSION)" $(if $(EPISODES),--max-episodes $(EPISODES),)

workflows-status:
	$(UV) run --locked python scripts/workflow_comparison.py status --session "$(WORKFLOW_SESSION)"

workflows-report:
	$(UV) run --locked python scripts/workflow_comparison.py report --session "$(WORKFLOW_SESSION)"

.PHONY: ui-record
ui-record:
	cd frontend && node scripts/record_walkthrough.mjs $(if $(RECORDING_OUTPUT),"$(RECORDING_OUTPUT)",)

.PHONY: resources-prepare resources-start resources-status resources-report
RESOURCE_SESSION ?= artifacts/pc-wsl/resource-completion-v1
resources-prepare:
	$(UV) run --locked python scripts/resource_completion.py prepare --session "$(RESOURCE_SESSION)" --model-profile "$(DECISION_PROFILE)" --sandbox-manifest "$(DECISION_SANDBOX)"

resources-start:
	$(UV) run --locked python scripts/resource_completion.py run --session "$(RESOURCE_SESSION)" $(if $(EPISODES),--max-episodes $(EPISODES),)

resources-status:
	$(UV) run --locked python scripts/resource_completion.py status --session "$(RESOURCE_SESSION)"

resources-report:
	$(UV) run --locked python scripts/resource_completion.py report --session "$(RESOURCE_SESSION)"
