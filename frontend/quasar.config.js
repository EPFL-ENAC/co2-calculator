/* eslint-env node */

/*
 * This file runs in a Node context (it's NOT transpiled by Babel), so use only
 * the ES6 features that are supported by your Node version. https://node.green/
 */

// Configuration for your app
// https://v2.quasar.dev/quasar-cli-vite/quasar-config-js

import { defineConfig } from '#q-app/wrappers';
// import { fileURLToPath } from 'node:url'

import path from 'path';

export default defineConfig(function (/* ctx */) {
  return {
    eslint: {
      // fix: true,
      // include: [],
      // exclude: [],
      // rawOptions: {},
      warnings: true,
      errors: true,
    },

    // https://v2.quasar.dev/quasar-cli-vite/prefetch-feature
    // preFetch: true,

    // app boot file (/src/boot)
    // --> boot files are part of "main.js"
    // https://v2.quasar.dev/quasar-cli-vite/boot-files
    boot: ['i18n', 'auth', 'workspace', 'router'],

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#css
    css: ['app.scss'],

    // https://github.com/quasarframework/quasar/tree/dev/extras
    extras: [
      'material-icons', // optional, you are not bound to it
      'material-icons-outlined',
    ],

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#build
    build: {
      target: {
        browser: ['es2019', 'edge88', 'firefox78', 'chrome87', 'safari13.1'],
        node: 'node22',
      },
      // alias: {
      //   maps: fileURLToPath(new URL('./src/maps', import.meta.url))
      // },

      vueRouterMode: 'history', // available values: 'hash', 'history'
      // vueRouterBase,
      // vueDevtools,
      // vueOptionsAPI: false,

      // rebuildCache: true, // rebuilds Vite/linter/etc cache on startup

      publicPath: '/',
      // analyze: true,
      env: {},
      // rawDefine: {}
      // ignorePublicFolder: true,
      minify: true,
      // polyfillModulePreload: true,
      // distDir
      sassVariables: 'src/css/quasar.variables.scss',
      // viteVuePluginOptions: {},

      vitePlugins: [
        [
          '@intlify/unplugin-vue-i18n/vite',
          {
            // if you want to use Vue I18n Legacy API, you need to set `compositionOnly: false`
            // compositionOnly: false,

            // if you want to use named tokens in your Vue I18n messages, such as 'Hello {name}',
            // you need to set `runtimeOnly: false`
            runtimeOnly: false,

            // you need to set i18n resource including paths !
            include: [
              path.resolve(__dirname, './src/i18n/**/*.json'),
              path.resolve(__dirname, './src/assets/i18n/**/*.json'),
              path.resolve(__dirname, './src/assets/i18n/**/*.md'),
            ],
          },
        ],
      ],
      extendViteConf(viteConf) {
        // Remove Quasar's auto-injected CSS
        if (!viteConf.css) viteConf.css = {};
        if (!viteConf.css.preprocessorOptions)
          viteConf.css.preprocessorOptions = {};
        if (!viteConf.css.preprocessorOptions.scss)
          viteConf.css.preprocessorOptions.scss = {};

        // Prevent Quasar from auto-injecting
        viteConf.resolve = viteConf.resolve || {};
        viteConf.resolve.alias = viteConf.resolve.alias || {};

        // Create an empty alias to block the auto-injection
        viteConf.resolve.alias['quasar/dist/quasar.sass'] = path.resolve(
          __dirname,
          './src/css/empty.scss',
        );
        viteConf.resolve.alias['quasar/dist/quasar.css'] = path.resolve(
          __dirname,
          './src/css/empty.scss',
        );
      },
    },

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#devServer
    devServer: {
      // https: true
      open: false, // opens browser window automatically
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#framework
    framework: {
      plugins: [
        'Dialog',
        'Loading',
        'Notify',
        'LocalStorage',
        'SessionStorage',
        'Meta',
      ],
      cssAddon: false,
      // override css!
      // config: {
      //   brand: {
      //     primary: 'rgb(244, 67, 54)',
      //     // ... other colors
      //   },
      // },
    },

    // animations: 'all', // --- includes all animations
    // https://v2.quasar.dev/options/animations
    animations: [],

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#sourcefiles
    // sourceFiles: {
    //   rootComponent: 'src/App.vue',
    //   router: 'src/router/index',
    //   store: 'src/store/index',
    //   registerServiceWorker: 'src-pwa/register-service-worker',
    //   serviceWorker: 'src-pwa/custom-service-worker',
    //   pwaManifestFile: 'src-pwa/manifest.json',
    //   electronMain: 'src-electron/electron-main',
    //   electronPreload: 'src-electron/electron-preload'
    // },

    // https://v2.quasar.dev/quasar-cli-vite/developing-ssr/configuring-ssr
    ssr: {
      // ssrPwaHtmlFilename: 'offline.html', // do NOT use index.html as name!
      // will mess up SSR

      // extendSSRWebserverConf (esbuildConf) {},
      // extendPackageJson (json) {},

      pwa: false,

      // manualStoreHydration: true,
      // manualPostHydrationTrigger: true,

      prodPort: 3000, // The default port that the production server should use
      // (gets superseded if process.env.PORT is specified at runtime)

      middlewares: [
        'render', // keep this as last one
      ],
    },

    // https://v2.quasar.dev/quasar-cli-vite/developing-pwa/configuring-pwa
    pwa: {
      workboxMode: 'generateSW', // or 'injectManifest'
      injectPwaMetaTags: true,
      swFilename: 'sw.js',
      manifestFilename: 'manifest.json',
      useCredentialsForManifestTag: false,
      // useFilenameHashes: true,
      // extendGenerateSWOptions (cfg) {}
      // extendInjectManifestOptions (cfg) {},
      // extendManifestJson (json) {}
      // extendPWACustomSWConf (esbuildConf) {}
    },

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/developing-cordova-apps/configuring-cordova
    // cordova: {
    //   // noIosLegacyBuildFlag: true, // uncomment only if you know what you are doing
    // },

    // // Full list of options: https://v2.quasar.dev/quasar-cli-vite/developing-capacitor-apps/configuring-capacitor
    // capacitor: {
    //   hideSplashscreen: true,
    // },

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/developing-electron-apps/configuring-electron
    // electron: {
    //   // extendElectronMainConf (esbuildConf)
    //   // extendElectronPreloadConf (esbuildConf)

    //   inspectPort: 5858,

    //   bundler: 'packager', // 'packager' or 'builder'

    //   packager: {
    //     // https://github.com/electron-userland/electron-packager/blob/master/docs/api.md#options
    //     // OS X / Mac App Store
    //     // appBundleId: '',
    //     // appCategoryType: '',
    //     // osxSign: '',
    //     // protocol: 'myapp://path',
    //     // Windows only
    //     // win32metadata: { ... }
    //   },

    //   builder: {
    //     // https://www.electron.build/configuration/configuration

    //     appId: 'co2-calculator'
    //   }
    // },

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/developing-browser-extensions/configuring-bex
    // bex: {
    //   contentScripts: ['my-content-script'],

    //   // extendBexScriptsConf (esbuildConf) {}
    //   // extendBexManifestJson (json) {}
    // },
  };
});
