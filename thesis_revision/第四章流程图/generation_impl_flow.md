```mermaid
graph TD
    A[输入问题 历史记录 证据列表] --> B[读取完整 Markdown<br/>缓存 full_content]
    B --> C[构造系统 Prompt<br/>限制仅依据参考资料回答]
    C --> D[拼接编号上下文<br/>[n] 来源 页码 内容]
    D --> E[LangChain 调用 Kimi API<br/>流式生成]
    E --> F[返回流式结果<br/>evidence 元数据 + answer]
    F --> G[Vue 解析引用标记<br/>[1][2] 转可点击按钮]
    G --> H[映射证据详情<br/>source pages full_content]
    H --> I[高亮原文并联动展示]
```
