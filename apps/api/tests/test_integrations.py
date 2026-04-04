from __future__ import annotations


def test_connect_and_sync_integration(client):
    auth_response = client.get('/api/v1/auth/google/callback', params={'code': 'dev_robert', 'state': 'gmail'})
    token = auth_response.json()['data']['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    connect_response = client.post('/api/v1/integrations/callback', json={'provider_key': 'gmail', 'code': 'dev_robert'}, headers=headers)
    assert connect_response.status_code == 200
    integration_id = connect_response.json()['data']['id']

    list_response = client.get('/api/v1/integrations', headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()['meta']['total'] == 1

    sync_response = client.post(f'/api/v1/integrations/{integration_id}/sync', headers=headers)
    assert sync_response.status_code == 200
    assert sync_response.json()['data']['saved_count'] >= 1

    activity_response = client.get('/api/v1/activity-logs', headers=headers)
    assert activity_response.status_code == 200
    assert activity_response.json()['meta']['total'] >= 1
