import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest) {
  const client_id = process.env.STRAVA_CLIENT_ID;
  const client_secret = process.env.STRAVA_CLIENT_SECRET;
  const refresh_token = process.env.STRAVA_REFRESH_TOKEN;


  if (!client_id || !client_secret || !refresh_token) {
    return NextResponse.json({
      error: 'Missing Strava API credentials.',
      client_id,
      client_secret,
      refresh_token
    }, { status: 500 });
  }

  // Get access token
  const auth_url = 'https://www.strava.com/oauth/token';
  const payload = {
    client_id,
    client_secret,
    refresh_token,
    grant_type: 'refresh_token',
    f: 'json',
  };


  let authRes, authData, access_token;
  try {
    authRes = await fetch(auth_url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    authData = await authRes.json();
    access_token = authData.access_token;
  } catch (err) {
    return NextResponse.json({ error: 'Error during auth fetch', details: String(err) }, { status: 500 });
  }
  if (!access_token) {
    return NextResponse.json({ error: 'Failed to get access token.', authData }, { status: 500 });
  }

  // Fetch activities
  const activities_url = 'https://www.strava.com/api/v3/athlete/activities?per_page=200&page=1';

  let activitiesRes, activities;
  try {
    activitiesRes = await fetch(activities_url, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    activities = await activitiesRes.json();
  } catch (err) {
    return NextResponse.json({ error: 'Error during activities fetch', details: String(err) }, { status: 500 });
  }

  if (!Array.isArray(activities)) {
    return NextResponse.json({ error: 'Activities response is not an array', activities }, { status: 500 });
  }

  return NextResponse.json({ activities });
}
