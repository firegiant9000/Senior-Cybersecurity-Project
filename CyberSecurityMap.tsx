// The real, maintained CyberSecurityMap component lives in the frontend source tree.
// Re-export it here so imports that reference `./components/CyberSecurityMap` at
// the repository root resolve to the working implementation.
export { default } from './frontend/src/components/charts/CyberSecurityMap';
