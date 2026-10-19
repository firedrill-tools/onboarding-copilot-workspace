import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, join } from 'node:path';
import { ApplicationError, commandMain, invokeCLI, privateDirectory } from './adapter-runtime.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const backend = existsSync(join(root, 'backend/pyproject.toml')) ? join(root, 'backend') : root;
const cases = new Set(JSON.parse(readFileSync(join(backend, 'data/index.json'))).cases.map(item => item.id));
const requestDriver = fileURLToPath(new URL('./request.py', import.meta.url));
export async function runApplication(input, parameters, signal, invocation) {
  if (Object.keys(input).some(key => !['caseId', 'action', 'message'].includes(key)) || !cases.has(input.caseId) || !['chat', 'inspect'].includes(input.action) ||
      (input.action === 'chat' ? typeof input.message !== 'string' || !input.message.trim() || input.message.length > 8000 || input.message.includes('\0') : input.message !== null)) throw new Error('Select a reviewed case and bounded chat message or explicit inspection; owner decisions are separate.');
  const directory = await privateDirectory(root, invocation), state = join(directory, 'workspace.json');
  const cli = ['uv', 'run', '--locked', '--no-sync'];
  try {
    await invokeCLI([...cli, 'onboarding-workspace', 'init', '--case', input.caseId, '--workspace', state], { cwd: backend, signal });
    const argv = [...cli, 'python', requestDriver, '--workspace', state, '--action', input.action];
    if (input.action === 'chat') argv.push('--message', input.message);
    const env = { ...process.env, ...(parameters.model ? { GEMINI_MODEL: parameters.model } : {}) };
    return { application: await invokeCLI(argv, { cwd: backend, signal, env }), localState: { directory, workspaceFile: state } };
  } catch (error) { if (error instanceof ApplicationError) error.evidence.runDirectory = directory; throw error; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await commandMain(runApplication);
