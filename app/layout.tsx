import './globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = {title:'AEGIS | Portfolio Risk Intelligence', description:'Explainable multi-agent portfolio risk assessment and scenario simulation.'};
export default function RootLayout({children}:{children:React.ReactNode}) {return <html lang="en"><body>{children}</body></html>}
