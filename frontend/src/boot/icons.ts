import { icons } from '@/plugin/module-icon';

export default ({ app }) => {
  app.config.globalProperties.$moduleIcons = icons;
};
