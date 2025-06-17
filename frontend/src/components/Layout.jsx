/** @jsx jsx */
/** @jsxFrag Fragment */
import { jsx, Fragment } from "hono/jsx"; // Import Hono's JSX runtime

export const Layout = (props) => (
    <html lang="en">
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            {/* <link rel="icon" href="/assets/favicon.png" /> */}
            <title>{props.title}</title>
            <meta name="description" content={props.desc} />
            <link rel="stylesheet" href="style.css" />
            {/* <script src="/htmx.min.js" defer></script> */}
            <script src="app.js"></script>
        </head>
        <body>
            <div>{props.children}</div>
        </body>
    </html>
);