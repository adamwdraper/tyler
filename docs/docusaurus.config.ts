import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'Tyler',
  tagline: 'A framework for manifesting AI agents with a complete lack of conventional limitations',
  favicon: 'img/tyler-soap.png',

  // Set the production url of your site here
  url: 'https://adamwdraper.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  baseUrl: '/tyler/',

  // Add head metadata for Algolia verification
  headTags: [
    {
      tagName: 'meta',
      attributes: {
        name: 'algolia-site-verification',
        content: '3CB619E37A467A60',
      },
    },
  ],

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'adamwdraper', // GitHub org/user name
  projectName: 'tyler', // repo name

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/adamwdraper/tyler/tree/main/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/tyler-social-card.jpg',
    // Add Algolia search configuration
    algolia: {
      appId: 'ZMNB566F0L',
      apiKey: '8700440be5b0c84b4fdd04f44efac6b1', // Search-only API key
      indexName: 'tyler',
    },
    navbar: {
      logo: {
        alt: 'Tyler Logo',
        src: 'img/tyler-soap.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'documentationSidebar',
          position: 'left',
          label: 'Documentation',
        },
        {
          type: 'docSidebar',
          sidebarId: 'apiSidebar',
          position: 'left',
          label: 'Reference',
        },
        {
          href: 'https://github.com/adamwdraper/tyler',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Introduction',
              to: '/docs/intro',
            },
            {
              label: 'Installation',
              to: '/docs/installation',
            },
            {
              label: 'Examples',
              to: '/docs/category/examples',
            },
          ],
        },
        {
          title: 'Reference',
          items: [
            {
              label: 'API Reference',
              to: '/docs/category/api-reference',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/adamwdraper/tyler',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Tyler. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
