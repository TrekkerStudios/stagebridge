/** @jsx jsx */
/** @jsxFrag Fragment */
/** @jsxImportSource hono/jsx */
import { jsx, Fragment } from "hono/jsx";
import { Hono } from "hono";
import { serveStatic } from 'hono/bun'

import './public/style.css';
import './public/main.js';

import { Layout } from "./components/Layout.jsx";
import { GeneratorPage } from "./components/GeneratorPage.jsx";

const app = new Hono();

app.use('/*', serveStatic({ root: './public' }))
// app.use('/favicon.ico', serveStatic({ path: './favicon.ico' }))

app.get("/", (c) => {
  return c.html(
    <Layout title="StageBridge Generator" desc="stagebridge dev">
      <GeneratorPage />
    </Layout>
  );
});

app.all('*', (c) => {
  const path = c.req.path;
  const referrer = c.req.header('referer') || 'direct';
  console.log(`Redirecting unmatched path: ${path} (referred from: ${referrer}) to homepage`);
  return c.redirect('/');
});

export default app;