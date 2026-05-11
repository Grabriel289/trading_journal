import { Chart as ChartJS } from 'chart.js';

/**
 * Apply Chart.js global defaults that match FRONTEND_DESIGN.md §8.1.
 * Imported once from main.jsx so every chart in the app inherits these.
 */
ChartJS.defaults.color = '#5a5c6a';
ChartJS.defaults.borderColor = 'rgba(255,255,255,0.03)';
ChartJS.defaults.font.family = '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif';
ChartJS.defaults.font.size = 11;

ChartJS.defaults.plugins.tooltip.backgroundColor = '#181924';
ChartJS.defaults.plugins.tooltip.borderColor = '#2a2c42';
ChartJS.defaults.plugins.tooltip.borderWidth = 1;
ChartJS.defaults.plugins.tooltip.titleColor = '#e8e9ed';
ChartJS.defaults.plugins.tooltip.bodyColor = '#8b8d9a';
ChartJS.defaults.plugins.tooltip.cornerRadius = 8;
ChartJS.defaults.plugins.tooltip.padding = 10;
ChartJS.defaults.plugins.tooltip.boxPadding = 6;
ChartJS.defaults.plugins.tooltip.titleFont = { size: 12, weight: 600 };
ChartJS.defaults.plugins.tooltip.bodyFont  = { size: 11 };
