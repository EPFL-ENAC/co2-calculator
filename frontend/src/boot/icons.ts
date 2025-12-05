import { icons } from 'src/plugin/module-icon';

export default ({ app }) => {
  app.config.globalProperties.$moduleIcons = icons;
};
