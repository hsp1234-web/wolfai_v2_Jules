import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ReportTabs from './ReportTabs';

// Mock report data for testing
const mockReport = {
  quantitative_summary: {
    metric1: 'Value 1',
    metric2: 'Value 2',
  },
  expert_opinions: [
    { expertName: 'Expert A', viewpoint: 'Viewpoint A', evidence: 'Evidence A' },
    { source: 'Source B', opinion: 'Opinion B', reasoning: 'Reasoning B' },
  ],
  ai_recommendations: [
    {
      strategy_name: 'Strategy Alpha',
      parameters: { paramA: '10' },
      see: 'See Alpha',
      think: 'Think Alpha',
      do: 'Do Alpha',
    },
  ],
};

const mockEmptyReport = {};

describe('ReportTabs Component', () => {
  test('renders correctly with full report data', () => {
    render(<ReportTabs report={mockReport} />);

    // Check if tab labels are present
    expect(screen.getByRole('tab', { name: '情境分析總結' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '高手觀點碰撞' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'AI 推薦策略' })).toBeInTheDocument();

    // Check if initial tab content (Tab 1) is visible
    expect(screen.getByText(/Metric1:/i)).toBeInTheDocument();
    expect(screen.getByText('Value 1')).toBeInTheDocument();
  });

  test('renders "No report data" message when report is null', () => {
    render(<ReportTabs report={null} />);
    expect(screen.getByText('No report data to display.')).toBeInTheDocument();
  });

  test('renders "No data available" messages for empty sections in Tab 1', () => {
    render(<ReportTabs report={mockEmptyReport} />);
    // Switch to Tab 1 (it's default, but good to be explicit if needed for other tests)
    fireEvent.click(screen.getByRole('tab', { name: '情境分析總結' }));
    expect(screen.getByText('此部分沒有可顯示的資料。')).toBeInTheDocument();
  });

  test('renders "No data available" messages for empty sections in Tab 2', () => {
    render(<ReportTabs report={mockEmptyReport} />);
    fireEvent.click(screen.getByRole('tab', { name: '高手觀點碰撞' }));
    expect(screen.getByText('此部分沒有可顯示的資料，或資料格式不符預期。')).toBeInTheDocument();
  });

  test('renders "No data available" messages for empty sections in Tab 3', () => {
    render(<ReportTabs report={mockEmptyReport} />);
    fireEvent.click(screen.getByRole('tab', { name: 'AI 推薦策略' }));
    expect(screen.getByText('此部分沒有可顯示的資料，或資料格式不符預期。')).toBeInTheDocument();
  });


  test('switches tabs and displays correct content', () => {
    render(<ReportTabs report={mockReport} />);

    // Click on Tab 2: "高手觀點碰撞"
    fireEvent.click(screen.getByRole('tab', { name: '高手觀點碰撞' }));
    expect(screen.getByText('Expert A')).toBeInTheDocument();
    expect(screen.getByText('Viewpoint A')).toBeInTheDocument();
    // Ensure Tab 1 content is not present
    expect(screen.queryByText(/Metric1:/i)).toBeNull();


    // Click on Tab 3: "AI 推薦策略"
    fireEvent.click(screen.getByRole('tab', { name: 'AI 推薦策略' }));
    expect(screen.getByText('Strategy Alpha')).toBeInTheDocument();
    expect(screen.getByText(/ParamA:/i)).toBeInTheDocument();
    expect(screen.getByText('See Alpha')).toBeInTheDocument();
    // Ensure Tab 2 content is not present
    expect(screen.queryByText('Expert A')).toBeNull();

    // Click back to Tab 1: "情境分析總結"
    fireEvent.click(screen.getByRole('tab', { name: '情境分析總結' }));
    expect(screen.getByText(/Metric1:/i)).toBeInTheDocument();
    // Ensure Tab 3 content is not present
    expect(screen.queryByText('Strategy Alpha')).toBeNull();
  });

  test('displays content correctly for Tab 1 (Quantitative Summary)', () => {
    render(<ReportTabs report={mockReport} />);
    fireEvent.click(screen.getByRole('tab', { name: '情境分析總結' })); // Ensure it's active
    expect(screen.getByText(/Metric1:/i)).toBeInTheDocument();
    expect(screen.getByText('Value 1')).toBeInTheDocument();
    expect(screen.getByText(/Metric2:/i)).toBeInTheDocument();
    expect(screen.getByText('Value 2')).toBeInTheDocument();
  });

  test('displays content correctly for Tab 2 (Expert Opinions)', () => {
    render(<ReportTabs report={mockReport} />);
    fireEvent.click(screen.getByRole('tab', { name: '高手觀點碰撞' })); // Ensure it's active
    expect(screen.getByText('Expert A')).toBeInTheDocument();
    expect(screen.getByText('Viewpoint A')).toBeInTheDocument();
    expect(screen.getByText('Evidence A')).toBeInTheDocument();
    expect(screen.getByText('Source B')).toBeInTheDocument(); // Testing fallback field name
    expect(screen.getByText('Opinion B')).toBeInTheDocument(); // Testing fallback field name
    expect(screen.getByText('Reasoning B')).toBeInTheDocument(); // Testing fallback field name
  });

  test('displays content correctly for Tab 3 (AI Recommended Strategies)', () => {
    render(<ReportTabs report={mockReport} />);
    fireEvent.click(screen.getByRole('tab', { name: 'AI 推薦策略' })); // Ensure it's active
    expect(screen.getByText('策略 1: Strategy Alpha')).toBeInTheDocument();
    expect(screen.getByText(/- ParamA: 10/i)).toBeInTheDocument(); // More specific to include key and colon
    expect(screen.getByText('See Alpha')).toBeInTheDocument();
    expect(screen.getByText('Think Alpha')).toBeInTheDocument();
    expect(screen.getByText('Do Alpha')).toBeInTheDocument();
  });

});
