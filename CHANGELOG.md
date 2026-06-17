# Changelog

## 0.0.0.1 - 2026-06-17

- Fixed the Agent Bootstrap response model to avoid Pydantic warnings from a field named `json` shadowing `BaseModel.json()`.
- Preserved the public bootstrap API response key as `json` through a Pydantic field alias.
- Added regression coverage that imports the models module with warnings treated as errors.
