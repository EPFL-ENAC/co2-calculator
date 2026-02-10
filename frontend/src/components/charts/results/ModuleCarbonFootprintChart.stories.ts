import type { Meta, StoryObj } from '@storybook/vue3';
import ModuleCarbonFootprintChart from './ModuleCarbonFootprintChart.vue';

/**
 * ModuleCarbonFootprintChart displays a stacked bar chart showing:
 * - Carbon footprint by category (Scope 1, 2, 3)
 * - Multiple subcategories within each category
 * - Optional uncertainty visualization
 * - Toggle for additional data categories
 * - Download options (PNG, CSV)
 *
 * ## Features
 * - Stacked bar chart with multiple series
 * - Scope 1, 2, 3 categorization
 * - Uncertainty visualization with mark lines
 * - Additional data toggle (commuting, food, waste, grey energy)
 * - Export functionality (PNG and CSV)
 */
const meta = {
  title: 'Charts/ModuleCarbonFootprintChart',
  component: ModuleCarbonFootprintChart,
  tags: ['autodocs'],
  argTypes: {
    viewUncertainties: {
      control: 'boolean',
      description: 'Show uncertainty visualization (mark lines)',
    },
  },
} satisfies Meta<typeof ModuleCarbonFootprintChart>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default chart without uncertainty visualization.
 */
export const Default: Story = {
  args: {
    viewUncertainties: false,
  },
  parameters: {
    layout: 'padded',
    viewport: {
      defaultViewport: 'xl-desktop',
    },
  },
};

/**
 * Chart with uncertainty visualization enabled.
 */
export const WithUncertainties: Story = {
  args: {
    viewUncertainties: true,
  },
  parameters: {
    layout: 'padded',
    viewport: {
      defaultViewport: 'xl-desktop',
    },
  },
};
