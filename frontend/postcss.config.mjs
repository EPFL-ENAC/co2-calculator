// https://github.com/michael-ciniawsky/postcss-load-config

import autoprefixer from 'autoprefixer';

// RTL support not needed for now. If it becomes required:
// 1. npm install postcss-rtlcss
// 2. add it to the plugins list below
// 3. optionally set quasar.config.js > framework > lang to an RTL language
export default {
  plugins: [
    autoprefixer({
      overrideBrowserslist: [
        'last 4 Chrome versions',
        'last 4 Firefox versions',
        'last 4 Edge versions',
        'last 4 Safari versions',
        'last 4 Android versions',
        'last 4 ChromeAndroid versions',
        'last 4 FirefoxAndroid versions',
        'last 4 iOS versions',
      ],
    }),
  ],
};
