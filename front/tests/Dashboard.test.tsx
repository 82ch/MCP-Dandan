import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import Dashboard from '../src/components/Dashboard';

describe('Dashboard Component', () => {
  it('renders without crashing', () => {
    const mockSetSelectedServer = vi.fn();
    const mockSetSelectedMessageId = vi.fn();
    const mockServers: any[] = [];

    const { container } = render(
      <Dashboard
        setSelectedServer={mockSetSelectedServer}
        servers={mockServers}
        setSelectedMessageId={mockSetSelectedMessageId}
      />
    );

    expect(container).toBeTruthy();
  });

  it('renders in tutorial mode', () => {
    const mockSetSelectedServer = vi.fn();
    const mockSetSelectedMessageId = vi.fn();
    const mockServers: any[] = [];

    const { container } = render(
      <Dashboard
        setSelectedServer={mockSetSelectedServer}
        servers={mockServers}
        setSelectedMessageId={mockSetSelectedMessageId}
        isTutorialMode={true}
      />
    );

    expect(container.querySelector('div')).toBeInTheDocument();
  });

  it('renders with servers', () => {
    const mockSetSelectedServer = vi.fn();
    const mockSetSelectedMessageId = vi.fn();
    const mockServers: any[] = [
      {
        id: 1,
        name: 'Test Server',
        type: 'mcp',
        icon: 'test-icon',
        tools: [],
      },
    ];

    const { container } = render(
      <Dashboard
        setSelectedServer={mockSetSelectedServer}
        servers={mockServers}
        setSelectedMessageId={mockSetSelectedMessageId}
      />
    );

    expect(container).toBeTruthy();
  });
});
