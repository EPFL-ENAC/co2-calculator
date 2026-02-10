import type { Meta, StoryObj } from '@storybook/vue3';
import BigNumber from './BigNumber.vue';

/**
 * BigNumber displays a large number with:
 * - Title label
 * - Large formatted number
 * - Optional unit label (defaults to tonnes)
 * - Optional comparison text
 * - Optional comparison highlight (bold text within comparison)
 * - Optional color for the number
 * - Optional tooltip slot
 *
 * ## Features
 * - Large, prominent number display
 * - Flexible comparison text with highlight support
 * - Color variants (positive, negative, primary, etc.)
 * - Tooltip support for additional information
 * - Responsive card layout
 */
const meta = {
  title: 'Molecules/BigNumber',
  component: BigNumber,
  tags: ['autodocs'],
  argTypes: {
    title: {
      control: 'text',
      description: 'Title label displayed above the number',
    },
    number: {
      control: 'text',
      description: 'The number to display (as string to preserve formatting)',
    },
    unit: {
      control: 'text',
      description: 'Unit label (defaults to tonnes if not provided)',
    },
    comparison: {
      control: 'text',
      description: 'Comparison text displayed on the right side',
    },
    comparisonHighlight: {
      control: 'text',
      description: 'Text within comparison to highlight (make bold)',
    },
    color: {
      control: 'select',
      options: ['primary', 'accent', 'negative', 'positive', 'warning', 'info'],
      description: 'Quasar color class for the number',
    },
  },
} satisfies Meta<typeof BigNumber>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default BigNumber with title and number only.
 */
export const Default: Story = {
  args: {
    title: 'Total Carbon Footprint',
    number: "37'250",
  },
};

/**
 * BigNumber with comparison text.
 */
export const WithComparison: Story = {
  args: {
    title: 'Total Carbon Footprint',
    number: "37'250",
    comparison: 'Equivalent to 109,559 km by car',
  },
};

/**
 * BigNumber with comparison highlight (bold text within comparison).
 */
export const WithComparisonHighlight: Story = {
  args: {
    title: 'Total Carbon Footprint',
    number: "37'250",
    comparison: 'Equivalent to 109,559 km by car',
    comparisonHighlight: '109,559 km',
  },
};

/**
 * Color variants showing different Quasar colors.
 */
export const ColorVariants: Story = {
  args: {
    title: 'Carbon Footprint',
    number: "37'250",
  },
  render: () => {
    const colors = [
      'primary',
      'accent',
      'negative',
      'positive',
      'warning',
      'info',
    ];
    return {
      components: { BigNumber },
      template: `
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 24px; padding: 24px;">
          <div v-for="color in colors" :key="color" style="display: flex; flex-direction: column; gap: 8px;">
            <BigNumber
              title="Carbon Footprint"
              number="37'250"
              :color="color"
            />
            <span style="font-size: 12px; color: #666; text-align: center;">{{ color }}</span>
          </div>
        </div>
      `,
      setup() {
        return { colors };
      },
    };
  },
};
