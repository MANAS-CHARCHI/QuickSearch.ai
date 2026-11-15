const API_BASE = '/api/v1';

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health/ready`);
    return await res.json();
  } catch (error) {
    return { status: 'error', checks: { error: String(error) } };
  }
}
