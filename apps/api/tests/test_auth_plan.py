from __future__ import annotations


def test_google_callback_creates_user_and_returns_plan(client):
    auth_response = client.get('/api/v1/auth/google/callback', params={'code': 'dev_robert', 'state': 'gmail'})
    assert auth_response.status_code == 200
    payload = auth_response.json()['data']
    token = payload['access_token']

    me_response = client.get('/api/v1/me', headers={'Authorization': f'Bearer {token}'})
    assert me_response.status_code == 200
    assert me_response.json()['data']['email'] == 'robert@example.com'

    plan_response = client.get('/api/v1/me/plan', headers={'Authorization': f'Bearer {token}'})
    assert plan_response.status_code == 200
    assert plan_response.json()['data']['plan_key'] == 'free'

    usage_response = client.get('/api/v1/me/usage', headers={'Authorization': f'Bearer {token}'})
    assert usage_response.status_code == 200
    assert usage_response.json()['data']['monthly_ai_quota'] == 20
