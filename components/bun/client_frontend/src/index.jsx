/** @jsx jsx */
/** @jsxFrag Fragment */
/** @jsxImportSource hono/jsx */
import { jsx } from "hono/jsx"; // Import Hono's JSX runtime
import { Hono } from "hono";
import { serveStatic } from 'hono/bun'

import { Layout } from "./components/Layout.jsx";
import { Content } from "./components/Content.jsx";

const app = new Hono();

app.use('/*', serveStatic({ root: './public' }))
// app.use('/favicon.ico', serveStatic({ path: './favicon.ico' }))

app.get("/", (c) => {
  return c.html(
    <Layout title="StageBridge" desc="stagebridge dev">
      <Content />
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