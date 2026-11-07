import type { NextConfig } from 'next';
const config: NextConfig = { async rewrites() { return process.env.BACKEND_URL ? [{source:'/api/:path*',destination:`${process.env.BACKEND_URL}/api/:path*`}] : []; } };
export default config;
