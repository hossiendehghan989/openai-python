from pathlib import Path

import httpx2
import pytest

from openai._exceptions import SubjectTokenProviderError
from openai.auth._workload import (
    gcp_id_token_provider,
    k8s_service_account_token_provider,
    azure_managed_identity_token_provider,
)


def error_client(status_code: int = 500) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status_code, request=request, text="metadata failure")

    return httpx2.Client(transport=httpx2.MockTransport(handler), trust_env=False)


@pytest.mark.parametrize(
    ("provider_factory", "message"),
    [
        (
            lambda client: azure_managed_identity_token_provider(http_client=client),
            "Failed to fetch Azure subject token from IMDS: HTTP 500",
        ),
        (
            lambda client: gcp_id_token_provider(http_client=client),
            "Failed to fetch GCP subject token from metadata server: HTTP 500",
        ),
    ],
)
def test_metadata_provider_preserves_error_response_and_message(provider_factory, message: str) -> None:
    with error_client() as client:
        with pytest.raises(SubjectTokenProviderError) as exc_info:
            provider_factory(client)["get_token"]()

    error = exc_info.value
    assert error.response is not None
    assert error.response.status_code == 500
    assert str(error) == message
    assert error.__cause__ is None


def test_k8s_provider_does_not_wrap_its_own_empty_file_error(tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("\n")

    with pytest.raises(SubjectTokenProviderError, match="The token file .* is empty") as exc_info:
        k8s_service_account_token_provider(token_file)["get_token"]()

    assert exc_info.value.__cause__ is None
