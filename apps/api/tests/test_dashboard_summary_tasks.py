from __future__ import annotations


def _auth_headers(client):
    auth_response = client.get('/api/v1/auth/google/callback', params={'code': 'dev_robert', 'state': 'gmail'})
    token = auth_response.json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}


def _connect_and_sync(client, headers):
    connect_response = client.post('/api/v1/integrations/callback', json={'provider_key': 'gmail', 'code': 'dev_robert'}, headers=headers)
    integration_id = connect_response.json()['data']['id']
    client.post(f'/api/v1/integrations/{integration_id}/sync', headers=headers)


def test_dashboard_and_summaries_and_tasks_flow(client):
    headers = _auth_headers(client)
    _connect_and_sync(client, headers)

    dashboard = client.get('/api/v1/dashboard', headers=headers)
    assert dashboard.status_code == 200
    payload = dashboard.json()['data']
    assert 'today_highlights' in payload
    assert payload['daily_summary_preview']['summary_id']

    summaries = client.get('/api/v1/summaries', headers=headers)
    assert summaries.status_code == 200
    assert summaries.json()['meta']['total'] >= 1
    summary_id = summaries.json()['data']['items'][0]['id']

    summary_detail = client.get(f'/api/v1/summaries/{summary_id}', headers=headers)
    assert summary_detail.status_code == 200
    assert len(summary_detail.json()['data']['items']) >= 1

    tasks = client.get('/api/v1/tasks', headers=headers)
    assert tasks.status_code == 200
    assert tasks.json()['meta']['total'] >= 1
    task_id = tasks.json()['data']['items'][0]['id']

    patch_resp = client.patch(f'/api/v1/tasks/{task_id}', json={'status': 'done', 'priority': 'medium'}, headers=headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()['data']['task']['status'] == 'done'
