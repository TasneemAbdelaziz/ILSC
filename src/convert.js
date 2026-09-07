/*
 * ILSC - Swagger 2.0 -> OpenAPI 3.x conversion (Sec. 7 pipeline, step b).
 *
 * Driven by src/convert.py, which passes a newline-delimited work list of
 * "<inputPath>\t<outputPath>" pairs. Everything runs in ONE node process:
 * spawning the swagger2openapi CLI per file costs ~0.3 s of startup each,
 * which dominates the actual conversion at corpus scale.
 *
 * Output is always JSON, so that specs/clean3/ is uniform for the parser.
 *
 *   node src/convert.js <worklist> <logfile>
 */

const fs = require('fs');
const converter = require('swagger2openapi');

const [, , worklist, logfile] = process.argv;

const jobs = fs
  .readFileSync(worklist, 'utf8')
  .split('\n')
  .map((l) => l.trim())
  .filter(Boolean)
  .map((l) => l.split('\t'));

// patch:   repair the small spec defects that would otherwise abort a convert
// warnOnly: record a problem and continue rather than throwing
// resolve/resolveInternal off: $ref resolution is the parser's job (prance),
//   and resolving here would inline schemas and silently change f5.
const options = { patch: true, warnOnly: true, resolve: false, resolveInternal: false };

const log = [];
let done = 0;

async function main() {
  for (const [inPath, outPath] of jobs) {
    try {
      const res = await converter.convertFile(inPath, { ...options });
      const spec = res.openapi;
      if (!spec || !spec.paths) throw new Error('no_paths_after_convert');
      fs.writeFileSync(outPath, JSON.stringify(spec), 'utf8');
      log.push([inPath, 'ok', '']);
    } catch (err) {
      const msg = String((err && err.message) || err).replace(/[\r\n\t,]+/g, ' ').slice(0, 200);
      log.push([inPath, 'failed', msg]);
    }
    done += 1;
    if (done % 50 === 0) process.stderr.write(`  ... converted ${done}/${jobs.length}\n`);
  }

  fs.writeFileSync(
    logfile,
    'input,status,detail\n' +
      log.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n') +
      '\n',
    'utf8'
  );
  const failed = log.filter((r) => r[1] === 'failed').length;
  process.stderr.write(`convert.js: ${log.length - failed} ok, ${failed} failed\n`);
}

main();
