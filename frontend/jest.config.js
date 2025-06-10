// jest.config.js
// Corrected import for next/jest
const nextJest = require('next/jest');

// Provide the path to your Next.js app to load next.config.js and .env files in your test environment
const createJestConfig = nextJest({
  dir: './',
});

// Add any custom config to be passed to Jest
/** @type {import('jest').Config} */
const customJestConfig = {
  testEnvironment: 'jest-environment-jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'], // if you have a setup file
  moduleNameMapper: {
    // Handle CSS imports (if you're not using CSS Modules or PostCSS with specific Jest transformers)
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    // Handle module aliases (if you have them in tsconfig.json)
    // Example: '^@/components/(.*)$': '<rootDir>/components/$1',
    // Example: '^@/app/(.*)$': '<rootDir>/app/$1', // For app router
  },
  // Add more setup options before each test is run
  // setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],

  // If using TypeScript with a baseUrl to set up directory aliases,
  // you need to configure moduleNameMapper to resolve those aliases in Jest.
  // modulePaths: ['<rootDir>'], // If your tsconfig.json has baseUrl: "."

  // Automatically clear mock calls, instances, contexts and results before every test
  clearMocks: true,
};

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
module.exports = createJestConfig(customJestConfig);
