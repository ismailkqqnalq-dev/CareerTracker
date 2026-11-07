MAX_GENERAL_BODY_BYTES = 1_048_576


def _large_valid_registration_body():
    prefix = (
        b'{"email":"body-limit@example.com",'
        b'"password":"StrongPass123","extra":"'
    )
    suffix = b'"}'
    return prefix + (b"x" * (MAX_GENERAL_BODY_BYTES + 1)) + suffix


def _chunked_large_registration_body():
    yield (
        b'{"email":"chunked-body-limit@example.com",'
        b'"password":"StrongPass123","extra":"'
    )
    for _ in range(17):
        yield b"x" * 65_536
    yield b'"}'


def test_general_request_body_limit_rejects_oversized_content_length(client):
    response = client.post(
        "/auth/register",
        content=_large_valid_registration_body(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413, response.text
    assert response.json()["error_code"] == "request_too_large"


def test_general_request_body_limit_counts_chunked_body_without_content_length(client):
    request = client.build_request(
        "POST",
        "/auth/register",
        content=_chunked_large_registration_body(),
        headers={"Content-Type": "application/json"},
    )
    assert "content-length" not in request.headers
    assert request.headers.get("transfer-encoding") == "chunked"

    response = client.send(request)

    assert response.status_code == 413, response.text
    assert response.json()["error_code"] == "request_too_large"


def test_ocr_and_job_analysis_keep_their_own_body_limits(client):
    oversized_length = str(MAX_GENERAL_BODY_BYTES + 1)

    ocr = client.post(
        "/ocr/extract",
        content=b"",
        headers={
            "Content-Type": "image/png",
            "Content-Length": oversized_length,
        },
    )
    job_analysis = client.post(
        "/job-analysis",
        content=b"{}",
        headers={
            "Content-Type": "application/json",
            "Content-Length": oversized_length,
        },
    )

    assert ocr.status_code == 401
    assert job_analysis.status_code == 401
