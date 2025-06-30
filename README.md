/**
 * @file Profile.ts
 * @description 个人简介
 */

interface Developer {
  name: string;
  title: string;
  location: string;
  languages: string[];
  skills: {
    frontend: string[];
    backend: string[];
    tools: string[];
  };
  contact: {
    email: string;
    website: string;
    linkedin: string;
  };
}

const profile: Developer = {
  name: "[你的名字]",
  title: "Frontend Engineer",
  location: "中国",
  languages: [
    "JavaScript",
    "TypeScript",
    "HTML",
    "CSS"
  ],
  skills: {
    frontend: [
      "React",
      "Vue",
      "Next.js",
      "微前端",
      "性能优化"
    ],
    backend: [
      "Node.js",
      "Express",
      "MongoDB"
    ],
    tools: [
      "Git",
      "Webpack",
      "Docker",
      "CI/CD"
    ]
  },
  contact: {
    email: "your.email@example.com",
    website: "https://your-website.com",
    linkedin: "https://linkedin.com/in/your-profile"
  }
}

console.log("Hello World! 👋")

while (alive) {
  eat();
  sleep();
  code();
  repeat();
}

// 当前状态
$ now-focusing --list
> 专注于前端工程化实践
> 探索 Web 性能优化
> 研究微前端架构

<div align="center">
  <img src="https://github-readme-stats.vercel.app/api?username=你的用户名&show_icons=true&theme=dark" height="165" />
</div>
