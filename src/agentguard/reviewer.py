"""Benchmark-only reviewer. Its input contract contains no attack objectives or grader data."""

from agentguard.contracts import (
    Contract,
    CreateAction,
    ShareAction,
    TaskContract,
    UpdateAction,
    digest,
)
from agentguard.storage import Store

REVIEWER_VERSION = "exact-action-reviewer-v2"


class ReviewContract(Contract):
    allowed_actions: tuple[CreateAction | UpdateAction | ShareAction, ...] = ()


class ExactActionReviewer:
    def __init__(self, task_contract: TaskContract, review_contract: ReviewContract):
        self.task_contract = task_contract
        self.allowed_hashes = {
            digest(action.model_dump(mode="json")) for action in review_contract.allowed_actions
        }

    def review(self, store: Store, request_id: str) -> bool:
        request = store.approval(request_id)
        snapshot = request["snapshot"]
        approved = (
            TaskContract.model_validate(snapshot["contract"]) == self.task_contract
            and digest(snapshot["action"]) in self.allowed_hashes
        )
        store.review(
            request_id,
            expected_hash=request["action_hash"],
            nonce=request["nonce"],
            reviewer=f"simulated:{REVIEWER_VERSION}",
            approve=approved,
        )
        return approved
