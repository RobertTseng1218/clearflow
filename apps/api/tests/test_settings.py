from __future__ import annotations


def _auth_headers(client):
    auth_response = client.get('/api/v1/auth/google/callback', params={'code': 'dev_robert', 'state': 'gmail'})
    token = auth_response.json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_settings_flow(client):
    headers = _auth_headers(client)

    settings_resp = client.get('/api/v1/settings', headers=headers)
    assert settings_resp.status_code == 200
    payload = settings_resp.json()['data']
    assert payload['plan']['plan_key'] == 'free'
    assert payload['profile']['timezone'] == 'Asia/Taipei'

    patch_resp = client.patch(
        '/api/v1/settings/notifications',
        json={'daily_summary_enabled': False, 'preferred_hour': 9},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()['data']['updated'] is True

    settings_resp = client.get('/api/v1/settings', headers=headers)
    payload = settings_resp.json()['data']
    assert payload['notification_preferences']['daily_summary_enabled'] is False
    assert payload['notification_preferences']['preferred_hour'] == 9
