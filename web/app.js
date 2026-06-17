const baseUrlInput = document.getElementById("baseUrl");
const apiKeyInput = document.getElementById("apiKey");
const agentNameInput = document.getElementById("agentName");
const workspaceQueryInput = document.getElementById("workspaceQuery");
const setupOutput = document.getElementById("setupOutput");
const smokeOutput = document.getElementById("smokeOutput");

baseUrlInput.value = window.location.origin;

async function api(path, options = {}) {
  const response = await fetch(baseUrlInput.value.replace(/\/$/, "") + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKeyInput.value,
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }
  if (!response.ok) {
    throw new Error(JSON.stringify(data, null, 2));
  }
  return data;
}

document.getElementById("runBootstrap").addEventListener("click", async () => {
  setupOutput.textContent = "Running bootstrap test...";
  try {
    const data = await api("/v1/bootstrap", {
      method: "POST",
      body: JSON.stringify({
        agent: {
          name: agentNameInput.value || "generic",
          capabilities: {
            can_read_markdown: true,
            can_parse_json: true,
            can_call_http: true,
            can_run_shell: false,
            can_install_skills: false,
            supports_mcp: false,
          },
        },
        workspace: {
          query: workspaceQueryInput.value || "personal cloud",
        },
        preferences: {
          max_contexts: 5,
          include_raw_logs: false,
          response_format: "markdown+json",
        },
      }),
    });
    setupOutput.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    setupOutput.textContent = error.message;
  }
});

document.getElementById("getPrompt").addEventListener("click", async () => {
  setupOutput.textContent = "Generating setup prompt...";
  try {
    const agent = encodeURIComponent(agentNameInput.value || "generic");
    const data = await api(`/v1/setup/prompt?agent_name=${agent}`);
    setupOutput.textContent = data.prompt;
  } catch (error) {
    setupOutput.textContent = error.message;
  }
});

document.getElementById("runSmoke").addEventListener("click", async () => {
  smokeOutput.textContent = "Running smoke tests...";
  try {
    const data = await api("/v1/tests/smoke");
    smokeOutput.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    smokeOutput.textContent = error.message;
  }
});
