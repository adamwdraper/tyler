import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'Tyler',
  tagline: 'A development kit for manifesting AI agents with a complete lack of conventional limitations',
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
          routeBasePath: '/',
          path: 'docs',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
        sitemap: {
          changefreq: 'weekly',
          priority: 0.5,
          ignorePatterns: ['/tags/**'],
          filename: 'sitemap.xml',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/tyler-social-card.jpg',
    // Add Algolia DocSearch configuration
    algolia: {
      appId: '2KCZHADPHX',
      apiKey: '8808c844b31a53e2f8206752cbed4ebc',
      indexName: 'adamwdraperio',
      contextualSearch: true,
    },
    navbar: {
      title: 'Tyler',
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
          sidebarId: 'referenceSidebar',
          position: 'left',
          label: 'Reference',
        },
        {
          type: 'search',
          position: 'right',
        },
        {
          href: 'https://github.com/adamwdraper/tyler',
          position: 'right',
          html: '<div style="display: flex; align-items: center; height: 32px;"><svg viewBox="0 0 24 24" width="20" height="20" style="margin: 0;"><path fill="currentColor" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.236 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg></div>',
        },
        {
          href: 'https://pypi.org/project/tyler-agent/',
          position: 'right',
          html: '<div style="display: flex; align-items: center; height: 32px;"><img src="https://img.shields.io/pypi/v/tyler-agent.svg?style=social" alt="PyPI version" style="margin: 0;" /></div>',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Sponsored by',
          items: [
            {
              html: '<a href="https://weave-docs.wandb.ai/" target="_blank" style="display: flex; align-items: center;"><img src="/tyler/img/weave_logo.png" alt="Weights & Biases Weave" height="40" /></a>',
            },
          ],
        },
        {
          title: 'Documentation',
          items: [
            {
              label: 'Introduction',
              to: '/',
            },
            {
              label: 'Installation',
              to: '/installation',
            },
            {
              label: 'Examples',
              to: '/category/examples',
            },
          ],
        },
        {
          title: 'Reference',
          items: [
            {
              label: 'API Reference',
              to: '/category/api-reference',
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
            {
              label: 'PyPI',
              href: 'https://pypi.org/project/tyler-agent/',
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
