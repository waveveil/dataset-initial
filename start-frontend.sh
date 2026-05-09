#!/bin/bash
cd "$(dirname "$0")/frontend"
npm install
npx vite --host
