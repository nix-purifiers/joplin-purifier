const fs = require('fs');
const path = require('path');
const assert = require('assert');

module.exports = async ({Setting, pluginService}) => {
  const id = 'io.github.jackgruber.combine-notes';
  const deadline = Date.now() + 60000;
  while (!pluginService.pluginById(id)?.running || !pluginService.allPluginsStarted) {
    if (Date.now() > deadline) throw new Error('Native plug-ins did not start');
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  const root = fs.realpathSync(process.env.JOPLIN_PURIFIER_ENVIRONMENT);
  assert.equal(Setting.value('pluginDir'), path.join(root, 'plugins'));
  assert.equal(Setting.value('plugins.devPluginPaths'), '');
  assert.deepEqual(Setting.value('startupDevPlugins'), []);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json'), 'utf8'));
  for (const builtin of Object.keys(manifest.builtin)) {
    assert(pluginService.pluginById(builtin).builtIn);
  }
  for (const method of ['loadPluginFromPackage', 'installPlugin',
    'installPluginFromRepo', 'updatePluginFromRepo', 'deletePluginFiles']) {
    await assert.rejects(pluginService[method]('not-a-package'), /plugins are locked/);
  }
  await assert.rejects(pluginService.loadPluginFromPath(__dirname), /Unlocked Joplin plugin path/);
  const data = pluginService.pluginById(id).dataDir;
  fs.mkdirSync(data, {recursive: true});
  const counterPath = path.join(data, 'purifier-counter');
  const count = fs.existsSync(counterPath) ? Number(fs.readFileSync(counterPath, 'utf8')) : 0;
  fs.writeFileSync(counterPath, String(count + 1));
  const expected = JSON.parse(fs.readFileSync(path.join(__dirname, 'counter.json'), 'utf8'));
  assert.equal(count + 1, expected);
  const setting = 'plugin-' + id + '.combinedNoteTitleCustom';
  if (count) assert.equal(Setting.value(setting), 'Counter ' + count);
  Setting.setValue(setting, 'Counter ' + (count + 1));
  const body = await new Promise((resolve, reject) => {
    require('http').get(process.env.PROBE_URL, response => {
      let text = '';
      response.on('data', data => text += data);
      response.on('end', () => resolve(text));
    }).on('error', reject);
  });
  assert.equal(body, 'ordinary HTTP works');
};
