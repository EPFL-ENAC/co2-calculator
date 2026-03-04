import type { Meta, StoryObj } from '@storybook/vue3';
import ModuleIcon from './ModuleIcon.vue';
import { icons } from 'src/plugin/module-icon';

/**
 * ModuleIcon displays SVG icons from the module-icon plugin.
 * Icons are dynamically loaded from the assets/icons/modules directory.
 *
 * ## Features
 * - Three size variants: sm, md, lg
 * - Customizable color via Quasar color classes
 * - All module icons available from the plugin
 */
const meta = {
  title: 'Atoms/ModuleIcon',
  component: ModuleIcon,
  tags: ['autodocs'],
  argTypes: {
    name: {
      control: 'select',
      options: Object.keys(icons),
      description: 'The name of the icon to display',
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size variant of the icon',
    },
    color: {
      control: 'text',
      description: 'Quasar color class (e.g., primary, accent, grey-8)',
    },
  },
} satisfies Meta<typeof ModuleIcon>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default ModuleIcon with medium size and accent color.
 */
export const Default: Story = {
  args: {
    name: 'headcount',
    size: 'md',
    color: 'accent',
  },
};

/**
 * All available module icons displayed in a grid.
 */
export const AllIcons: Story = {
  args: {
    name: 'headcount',
  },
  render: () => {
    const iconNames = Object.keys(icons);
    return {
      components: { ModuleIcon },
      template: `
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 24px; padding: 24px;">
          <div v-for="iconName in iconNames" :key="iconName" style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            <ModuleIcon :name="iconName" size="md" color="accent" />
            <span style="font-size: 12px; text-align: center; word-break: break-word;">{{ iconName }}</span>
          </div>
        </div>
      `,
      setup() {
        return { iconNames };
      },
    };
  },
};

/**
 * Size variants: small, medium, and large.
 */
export const SizeVariants: Story = {
  args: {
    name: 'headcount',
  },
  render: () => {
    const iconNames = Object.keys(icons);
    const sizes: Array<'sm' | 'md' | 'lg'> = ['sm', 'md', 'lg'];
    return {
      components: { ModuleIcon },
      template: `
        <div style="padding: 24px;">
          <div v-for="iconName in iconNames" :key="iconName" style="display: flex; align-items: center; gap: 24px; margin-bottom: 24px; padding: 16px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="min-width: 100px; font-weight: 500;">{{ iconName }}</div>
            <div v-for="size in sizes" :key="size" style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
              <ModuleIcon :name="iconName" :size="size" color="accent" />
              <span style="font-size: 11px; color: #666;">{{ size }}</span>
            </div>
          </div>
        </div>
      `,
      setup() {
        return { iconNames, sizes };
      },
    };
  },
};

/**
 * Color variants showing different Quasar color classes.
 */
export const ColorVariants: Story = {
  args: {
    name: 'headcount',
  },
  render: () => {
    const iconNames = Object.keys(icons);
    const colors = ['primary', 'accent', 'grey-8', 'info'];
    return {
      components: { ModuleIcon },
      template: `
        <div style="padding: 24px;">
          <div v-for="iconName in iconNames" :key="iconName" style="display: flex; align-items: center; gap: 24px; margin-bottom: 24px; padding: 16px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="min-width: 150px; font-weight: 500;">{{ iconName }}</div>
            <div v-for="color in colors" :key="color" style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
              <ModuleIcon :name="iconName" size="md" :color="color" />
              <span style="font-size: 11px; color: #666;">{{ color }}</span>
            </div>
          </div>
        </div>
      `,
      setup() {
        return { iconNames, colors };
      },
    };
  },
};
