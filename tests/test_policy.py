import pytest

from agentguard.contracts import CreateAction, CreateArguments, Document, Project, digest
from agentguard.policy import evaluate


@pytest.mark.parametrize("profile", ["baseline", "prompt_only", "defended"])
@pytest.mark.parametrize("mismatch", ["workspace", "target", "type"])
def test_resolution_must_match_action_and_workspace(contract, profile, mismatch):
    resource = Project(id="atlas", workspace="lab", writers=("alex",))
    if mismatch == "workspace":
        resource = resource.model_copy(update={"workspace": "other"})
    elif mismatch == "target":
        resource = resource.model_copy(update={"id": "other"})
    else:
        resource = Document(id="atlas", workspace="lab", body="private", readers=("alex",))
    result = evaluate(
        episode_id="episode",
        contract=contract,
        profile=profile,
        action=CreateAction(arguments=CreateArguments(project_id="atlas", title="x", body="x")),
        resource=resource,
        confidential=False,
    )
    assert result.reason == "RESOURCE_UNAVAILABLE"


def test_unknown_profile_fails_closed(contract, projects):
    result = evaluate(
        episode_id="episode",
        contract=contract,
        profile="defendde",
        action=CreateAction(arguments=CreateArguments(project_id="atlas", title="x", body="x")),
        resource=projects[0],
        confidential=False,
    )
    assert result.reason == "UNKNOWN_PROFILE"


def test_canonical_hash_ignores_key_order_but_preserves_content():
    assert digest({"a": 1, "b": "x"}) == digest({"b": "x", "a": 1})
    assert digest({"body": "x"}) != digest({"body": " x "})
