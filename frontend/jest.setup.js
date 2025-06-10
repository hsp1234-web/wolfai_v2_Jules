// jest.setup.js
// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

// Optional: Mock global fetch if you want a default mock for all tests,
// though it's often better to mock it specifically in tests that need it.
/*
global.fetch = jest.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({ mockData: true }),
    ok: true,
  })
);
*/

// You can add other global setup here if needed.
// For example, silencing expected console errors in tests:
/*
let originalError;
beforeAll(() => {
  originalError = console.error;
  console.error = (...args) => {
    if (/Warning: ReactDOM.render is no longer supported in React 18./.test(args[0])) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});
*/
