import type { Meta, StoryObj } from '@storybook/vue3';
import CO2Container from './CO2Container.vue';

/**
 * CO2Container is a simple wrapper component that provides container styling.
 * It uses a single slot to wrap any content with the container layout styles.
 *
 * ## Features
 * - Single slot for flexible content
 * - Applies container layout styling
 * - Reusable wrapper for consistent spacing and layout
 */
const meta = {
  title: 'Atoms/CO2Container',
  component: CO2Container,
  tags: ['autodocs'],
} satisfies Meta<typeof CO2Container>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default CO2Container with simple content.
 */
export const Default: Story = {
  render: () => ({
    components: { CO2Container },
    template: `
      <CO2Container>
        <span>This is content inside the CO2Container.</span>
      </CO2Container>
    `,
  }),
};

/**
 * CO2Container with multiple elements to demonstrate layout.
 */
export const WithMultipleElements: Story = {
  render: () => ({
    components: { CO2Container },
    template: `
      <CO2Container>
        <h2>Container Title</h2>
        <span>This container can hold multiple elements.</span>
      </CO2Container>
    `,
  }),
};
