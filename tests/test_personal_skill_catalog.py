from app.main import app
from app.database.session import get_db
from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.skills import (
    PersonalSkillAlias,
    Skill,
    SkillAliases,
    UserSkill,
)
from app.models.users import User
from app.services.skill_catalog_service import seed_skill_catalog
from app.services.skill_normalizer import find_skill
from tests.test_skills_api import _create_opportunity


def second_headers(client):
    assert client.post('/auth/register', json={
        'email': 'other@example.com', 'password': 'StrongPass123',
    }).status_code == 201
    response = client.post('/auth/token', data={
        'username': 'other@example.com', 'password': 'StrongPass123',
    })
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def test_created_skill_is_private_and_names_can_repeat(authenticated_client):
    client = authenticated_client
    first = client.post('/skills', json={'name': 'Private Tool'}).json()
    other = second_headers(client)
    assert client.get('/skills', headers=other).json() == []
    assert client.get('/skills/resolve', params={'name': 'Private Tool'}, headers=other).status_code == 404
    public = type(client)(app)
    assert public.get('/skills').json() == []
    assert public.get('/skills/resolve', params={'name': 'Private Tool'}).status_code == 404
    second = client.post('/skills', json={'name': 'Private Tool'}, headers=other)
    assert second.status_code == 201
    assert second.json()['id'] != first['id']
    assert client.get('/skills').json() == [first]
    assert client.get('/skills/resolve', params={'name': 'PRIVATE TOOL'}).json()['id'] == first['id']


def test_create_skill_conflicting_with_shared_python_returns_409(authenticated_client):
    client = authenticated_client
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    seed_skill_catalog(db)
    generator.close()

    response = client.post('/skills', json={'name': 'Python'})

    assert response.status_code == 409


def test_alias_to_shared_skill_is_private(authenticated_client):
    client = authenticated_client
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    seed_skill_catalog(db)
    python = find_skill(db, 'Python').id
    postgres = find_skill(db, 'PostgreSQL').id
    other = second_headers(client)
    assert client.post(f'/skills/{python}/aliases', json={'alias': 'My Tool'}).status_code == 201
    assert client.get('/skills/resolve', params={'name': 'My Tool'}, headers=other).status_code == 404
    assert type(client)(app).get('/skills/resolve', params={'name': 'My Tool'}).status_code == 404
    assert client.post(f'/skills/{postgres}/aliases', json={'alias': 'My Tool'}, headers=other).status_code == 201
    assert client.get('/skills/resolve', params={'name': 'My Tool'}).json()['id'] == python
    assert client.get('/skills/resolve', params={'name': 'My Tool'}, headers=other).json()['id'] == postgres
    assert db.query(SkillAliases).filter(SkillAliases.alias == 'my tool').count() == 0
    assert find_skill(db, 'Python').id == python
    generator.close()


def test_private_skill_cannot_be_used_by_another_user(authenticated_client):
    client = authenticated_client
    skill_id = client.post('/skills', json={'name': 'Secret Tool'}).json()['id']
    other = second_headers(client)
    suggestion = client.post('/skills/suggestions', json={'skill': 'Secret Tool Variant'}, headers=other).json()
    assert client.get(f"/skills/suggestions/{suggestion['id']}/candidates", headers=other).json() == []
    assert client.post(f'/skills/{skill_id}/aliases', json={'alias': 'Stolen'}, headers=other).status_code == 404
    assert client.post('/users/me/skills', json={'skill_id': skill_id}, headers=other).status_code == 404
    assert client.patch(f"/skills/suggestions/{suggestion['id']}", json={'skill_id': skill_id}, headers=other).status_code == 404
    assert client.post('/users/me/skills', json={'skill_id': skill_id}).status_code == 201


def test_seed_does_not_adopt_personal_skills_or_aliases(authenticated_client):
    client = authenticated_client
    private = client.post('/skills', json={'name': 'Python', 'category': 'personal'}).json()
    assert client.post(f"/skills/{private['id']}/aliases", json={'alias': 'postgres'}).status_code == 201
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    seed_skill_catalog(db)
    shared = find_skill(db, 'Python')
    assert shared.id != private['id']
    assert find_skill(db, 'postgres').name == 'PostgreSQL'
    assert client.get('/skills/resolve', params={'name': 'Python'}).json()['id'] == private['id']
    assert db.get(Skill, private['id']).category == 'personal'
    generator.close()


def test_alias_matching_pending_suggestion_keeps_it_pending(authenticated_client):
    client = authenticated_client
    skill = client.post('/skills', json={'name': 'Target Skill'}).json()
    suggestion = client.post(
        '/skills/suggestions',
        json={'skill': 'My Pending Alias'},
    ).json()

    added_alias = client.post(
        f"/skills/{skill['id']}/aliases",
        json={'alias': 'My Pending Alias'},
    )

    assert added_alias.status_code == 201
    assert client.get(
        '/skills/resolve',
        params={'name': 'My Pending Alias'},
    ).json()['id'] == skill['id']
    suggestions = client.get('/skills/suggestions').json()
    matching = next(row for row in suggestions if row['id'] == suggestion['id'])
    assert matching['status'] == 'pending'


def test_personal_alias_does_not_influence_other_users_candidates(authenticated_client):
    client = authenticated_client
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    seed_skill_catalog(db)
    skill_id = find_skill(db, 'Python').id
    other = second_headers(client)
    own = client.post('/skills/suggestions', json={'skill': 'zzqqvv'}).json()['id']
    theirs = client.post('/skills/suggestions', json={'skill': 'zzqqvv'}, headers=other).json()['id']
    assert client.post(f'/skills/{skill_id}/aliases', json={'alias': 'zzqqvv'}).status_code == 201
    candidates = client.get(f'/skills/suggestions/{own}/candidates').json()
    assert candidates[0]['id'] == skill_id
    assert candidates[0]['score'] == 1
    assert client.get(f'/skills/suggestions/{theirs}/candidates', headers=other).json() == []
    generator.close()


def test_personal_alias_can_override_shared_alias_only_for_owner(authenticated_client):
    client = authenticated_client
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    seed_skill_catalog(db)
    python = find_skill(db, 'Python').id
    postgres = find_skill(db, 'postgres').id
    other = second_headers(client)
    assert client.post(f'/skills/{python}/aliases', json={'alias': 'postgres'}).status_code == 201
    assert client.get('/skills/resolve', params={'name': 'postgres'}).json()['id'] == python
    assert client.get('/skills/resolve', params={'name': 'postgres'}, headers=other).json()['id'] == postgres
    assert find_skill(db, 'postgres').id == postgres
    generator.close()


def test_opportunity_private_skill_attachment_is_scoped(authenticated_client):
    client = authenticated_client
    skill = client.post('/skills', json={'name': 'Private Tool'}).json()
    opportunity = _create_opportunity(client)
    assert client.post(f'/opportunities/{opportunity}/skills', json={'skill': 'Private Tool'}).status_code == 201
    assert client.get(f'/opportunities/{opportunity}/skills').json() == [skill]
    other = second_headers(client)
    assert client.get(f'/opportunities/{opportunity}/skills', headers=other).status_code == 404
    client.headers.update(other)
    their_opportunity = _create_opportunity(client)
    response = client.post(f'/opportunities/{their_opportunity}/skills', json={'skill': 'Private Tool'})
    assert response.status_code == 404
    assert client.get(f'/opportunities/{their_opportunity}/skills').json() == []
    assert client.get('/skills/suggestions').json()[0]['status'] == 'pending'


def test_opportunity_reads_hide_injected_other_users_private_skill(authenticated_client):
    client = authenticated_client
    other = second_headers(client)
    their_private = client.post(
        '/skills',
        json={'name': 'Owner B private skill'},
        headers=other,
    ).json()
    opportunity_id = _create_opportunity(client)

    # Simulate a stale or incorrectly written association in the database.
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    db.add(OpportunitySkill(
        opportunity_id=opportunity_id,
        skill_id=their_private['id'],
    ))
    db.commit()
    generator.close()

    listed = client.get(f'/opportunities/{opportunity_id}/skills')
    matched = client.get(f'/opportunities/{opportunity_id}/skill-match')

    assert listed.status_code == 200
    assert [skill['id'] for skill in listed.json()] == []
    assert matched.status_code == 200
    assert matched.json()['required_skill_count'] == 0
    assert matched.json()['missing_skills'] == []


def test_deleting_user_cascades_private_skill_alias_and_links(db_session):
    user = User(email='cascade@example.test', hashed_password='unused')
    db_session.add(user)
    db_session.commit()

    skill = Skill(name='Private cascade skill', owner_user_id=user.id)
    opportunity = Opportunity(user_id=user.id, company='Test', position='Test')
    db_session.add_all([skill, opportunity])
    db_session.commit()
    db_session.add_all([
        PersonalSkillAlias(
            user_id=user.id,
            alias='private cascade alias',
            skill_id=skill.id,
        ),
        UserSkill(
            user_id=user.id,
            skill_id=skill.id,
            proficiency_level='beginner',
            years_experience=0,
        ),
        OpportunitySkill(
            opportunity_id=opportunity.id,
            skill_id=skill.id,
        ),
    ])
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(Skill).filter_by(name='Private cascade skill').count() == 0
    assert db_session.query(PersonalSkillAlias).filter_by(alias='private cascade alias').count() == 0
    assert db_session.query(UserSkill).count() == 0
    assert db_session.query(OpportunitySkill).count() == 0
    assert db_session.query(Opportunity).count() == 0
