import type { Meta, StoryObj } from '@storybook/vue3';
import ModuleCarbonFootprintChart from './ModuleCarbonFootprintChart.vue';

/**
 * ModuleCarbonFootprintChart displays a stacked bar chart showing:
 * - Carbon footprint by category (Scope 1, 2, 3)
 * - Multiple subcategories within each category
 * - Toggle for additional data categories
 * - Download options (PNG, CSV)
 *
 * ## Features
 * - Stacked bar chart with multiple series
 * - Scope 1, 2, 3 categorization
 * - Additional data toggle (commuting, food, waste, grey energy)
 * - Export functionality (PNG and CSV)
 */
const meta = {
  title: 'Charts/ModuleCarbonFootprintChart',
  component: ModuleCarbonFootprintChart,
  tags: ['autodocs'],
} satisfies Meta<typeof ModuleCarbonFootprintChart>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default chart.
 */
export const Default: Story = {
  parameters: {
    layout: 'padded',
  },

  globals: {
    viewport: {
      value: 'xl-desktop',
      isRotated: false,
    },
  },
};
