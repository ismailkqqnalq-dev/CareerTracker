from app.database.session import get_db
from app.main import app
from app.models.skills import SkillSuggestion
from app.models.users import User
from app.services.skill_normalizer import normalize_text


def _create_skill(client, name):
    response = client.post('/skills', json={'name': name})
    assert response.status_code == 201, response.text
    return response.json()


def _pending_suggestion(client, email, raw_name):
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        user = db.query(User).filter(User.email == email).one()
        suggestion = SkillSuggestion(
            user_id=user.id,
            raw_name=raw_name,
            normalized_name=normalize_text(raw_name),
            status='pending',
        )
        db.add(suggestion)
        db.commit()
        return suggestion.id
    finally:
        generator.close()


def _candidate_response(client, suggestion_id):
    return client.get(f'/skills/suggestions/{suggestion_id}/candidates')


def test_csharp_is_ranked_above_cpp(authenticated_client):
    client = authenticated_client
    csharp = _create_skill(client, 'C#')
    cpp = _create_skill(client, 'C++')
    _create_skill(client, 'R')
    _create_skill(client, 'Python')
    suggestion_id = _pending_suggestion(client, 'owner@example.com', 'C#')

    response = _candidate_response(client, suggestion_id)

    assert response.status_code == 200
    candidates = response.json()
    assert candidates[0]['id'] == csharp['id']
    cpp_candidate = next(candidate for candidate in candidates if candidate['id'] == cpp['id'])
    assert cpp_candidate['score'] < candidates[0]['score'] - 0.2


def test_cpp_is_ranked_above_csharp(authenticated_client):
    client = authenticated_client
    _create_skill(client, 'C#')
    cpp = _create_skill(client, 'C++')
    _create_skill(client, 'R')
    suggestion_id = _pending_suggestion(client, 'owner@example.com', 'C++')

    response = _candidate_response(client, suggestion_id)

    assert response.status_code == 200
    assert response.json()[0]['id'] == cpp['id']


def test_r_is_a_candidate_for_exact_single_letter_query(authenticated_client):
    client = authenticated_client
    r_skill = _create_skill(client, 'R')
    _create_skill(client, 'Python')
    suggestion_id = _pending_suggestion(client, 'owner@example.com', 'R')

    response = _candidate_response(client, suggestion_id)

    assert response.status_code == 200
    assert response.json()[0]['id'] == r_skill['id']
    assert response.json()[0]['score'] == 1


def test_symbol_only_query_returns_empty_candidates(authenticated_client):
    client = authenticated_client
    _create_skill(client, 'C#')
    _create_skill(client, 'C++')
    suggestion_id = _pending_suggestion(client, 'owner@example.com', '++')

    response = _candidate_response(client, suggestion_id)

    assert response.status_code == 200
    assert response.json() == []


def test_private_csharp_skill_is_not_visible_in_another_users_candidates(client):
    client.post(
        '/auth/register',
        json={'email': 'first@example.com', 'password': 'StrongPass123'},
    )
    first_token = client.post(
        '/auth/token',
        data={'username': 'first@example.com', 'password': 'StrongPass123'},
    ).json()['access_token']
    first_headers = {'Authorization': f'Bearer {first_token}'}
    private_csharp = client.post(
        '/skills',
        json={'name': 'C#'},
        headers=first_headers,
    ).json()

    client.post(
        '/auth/register',
        json={'email': 'second@example.com', 'password': 'StrongPass123'},
    )
    second_token = client.post(
        '/auth/token',
        data={'username': 'second@example.com', 'password': 'StrongPass123'},
    ).json()['access_token']
    client.headers.update({'Authorization': f'Bearer {second_token}'})
    _create_skill(client, 'C++')
    suggestion_id = _pending_suggestion(client, 'second@example.com', 'C#')

    response = _candidate_response(client, suggestion_id)

    assert response.status_code == 200
    assert private_csharp['id'] not in {candidate['id'] for candidate in response.json()}
