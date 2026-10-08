import { readFileSync, writeFileSync } from 'node:fs';

const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
const packages = Object.entries(lock.packages)
  .filter(([path]) => path)
  .map(([path, value]) => ({
    package: path.replace(/^node_modules\//, ''),
    version: value.version,
    license: value.license ?? 'Review package metadata',
    development: !!value.dev,
    integrity: value.integrity,
  }));
writeFileSync(
  new URL('../../docs/frontend-dependency-licenses.json', import.meta.url),
  JSON.stringify(
    {
      source:
        'npm package-lock.json metadata, including development and platform-optional dependencies. Not a legal review.',
      packages,
    },
    null,
    2,
  ) + '\n',
);
