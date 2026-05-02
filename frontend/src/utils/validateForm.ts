export interface ValidationError {
  field: string;
  message: string;
}

export function validateSessionName(name: string): ValidationError | null {
  if (!name || name.trim().length === 0) {
    return { field: 'name', message: 'Session name is required' };
  }
  if (name.trim().length < 2) {
    return { field: 'name', message: 'Session name must be at least 2 characters' };
  }
  return null;
}

export function validateFile(file: File | null): ValidationError | null {
  if (!file) {
    return { field: 'file', message: 'Please select an audio file' };
  }
  const validTypes = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/x-m4a'];
  const validExtensions = ['.mp3', '.wav', '.m4a'];
  const hasValidType = validTypes.includes(file.type);
  const hasValidExt = validExtensions.some(ext => file.name.toLowerCase().endsWith(ext));

  if (!hasValidType && !hasValidExt) {
    return { field: 'file', message: 'Supported formats: mp3, wav, m4a' };
  }
  return null;
}

export function validateScenarioPrompt(prompt: string): ValidationError | null {
  if (!prompt || prompt.trim().length === 0) {
    return { field: 'prompt', message: 'Please describe the scenario' };
  }
  if (prompt.trim().length < 10) {
    return { field: 'prompt', message: 'Please provide a more detailed description' };
  }
  return null;
}
