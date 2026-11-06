import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./browser/e2e',timeout:45000,workers:1,retries:0,reporter:'list',use:{trace:'retain-on-failure'}});
