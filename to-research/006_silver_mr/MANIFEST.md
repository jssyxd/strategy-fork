# Silver SMR Production Package Manifest (物理清单)

**版本:** 1.0.0-prod  
**生成时间:** 2026-10-24T06:54:37Z  
**收录文件总数:** 23 个  

| 相对路径 | 文件大小 (Bytes) | SHA-256 完整校验和 | 模块说明 |
| :--- | :--- | :--- | :--- |
| `README.md` | 10,583 | `9ee7be148397d792216c4748e4ec291de0dd251de9450381821a62e56d8f054b` | 生产级系统架构与使用说明书 |
| `data/SILVER_AG_2yr_15m.parquet` | 4,203,265 | `3a45a8c0e3883ba6a9f4d3d3eb34b1a7183d1de83be7e1e8003f649f14cdbdd4` | 连续 2 年 15m 白银全量治理数据集 (72,193 根) |
| `docs/KAGGLE_RESOURCES.md` | 3,194 | `f2596e16ead2366a6bf89c8f954cb5b9b5119331f86921c026d5c5c3f213ce3d` | Kaggle 资源与算力适配文档 |
| `docs/SMR_AUDIT_REPORT.md` | 792 | `ece9b2942e6f2c83254c3c675f7298df0cabcee7a7f58ff9cd06ea17b1e09add` | 原始白银策略审计报告 |
| `docs/THEORY_PAPERS.md` | 2,301 | `c8f8d28bcf9149a47a066b28f03b303a5804279b83e49e6dd79d67c53d6768bc` | Avellaneda-Stoikov 学术论文推导索引 |
| `docs/papers/1011.6402.pdf` | 741,640 | `40d1d5f0baf7944a1b9f4c12d3644038e657acf4a3dfb500b2057c2269edd25f` | 相关学术文献/原件 |
| `docs/papers/1105.1694.pdf` | 714,833 | `02816232ce7b934869fa5ae8f1582bfdc0729d9d3378f0b8089eab538f923ea8` | 相关学术文献/原件 |
| `docs/papers/1105.3115.pdf` | 847,535 | `e3d8348e0a3ac0599d30ea56ac7420161979b74b0ddbb788d6800779366f6912` | 相关学术文献/原件 |
| `docs/papers/2002.05715.pdf` | 1,393,673 | `d542aea8329ef78d8c822948876b83402dfacb09955970ae5238ac5618bb7d28` | 相关学术文献/原件 |
| `docs/papers/2207.09951.pdf` | 432,563 | `356940aaedbae4a2530d13db2fb7aa487dde1fdcf0acac4d0d774fe71561846c` | 相关学术文献/原件 |
| `engine/__init__.py` | 541 | `87bcf2950f7a4af2912b4eb6ce8113935d4fdc10293820be552beeef1ceaf356` | 引擎模块统一导出定义 |
| `engine/as_discrete_linear_engine.py` | 4,856 | `e3892c257a1300bf1d2f3dbb3381c4575da4ecb02325675e6110b1cec0a76a34` | 离散非对称 A-S 网格做市内核 |
| `engine/dynamic_smr_runner.py` | 10,831 | `87cc62e166fa10b649ad2d1316b3ecea124dfff3e07d262e1efb31684633aa3b` | 四级事件驱动 MLOps 状态机与回测执行器 |
| `engine/fifo_accounting.py` | 5,391 | `d4afaba3c2dde4f236efcdbd261196533fd0abab7a563e4c5e59963eb1c01d2b` | 严格 FIFO 往返记账与逆向选择审计器 |
| `engine/mle_intensity_estimator.py` | 2,123 | `1ae33fa193eb2c4c7140f9b12567e17c4c9eaea168ffd4274681296604d23001` | 极大似然估计跳价强度求解器 |
| `generate_manifest.py` | 3,330 | `6661b10596e7f0cf6e99ad00a25efbc10013172ff72a9bcf87f6fbf4ba88ded2` | 相关学术文献/原件 |
| `kaggle_trainer/kernel-metadata.json` | 339 | `6e0a73f27d76007175fdd5f9710539ff1e2c2a1cdb6e2fbc13bcdb7d190f0c99` | Kaggle Kernel 配置元数据 |
| `kaggle_trainer/silver-smr-as-gatekeeper-trainer.log` | 3,243 | `7caf78c8b5cc09a3b04605343a7e7d00a75731dd6222c3b7082783e63747b3ac` | Kaggle 云端容器完整运行控制台日志 |
| `kaggle_trainer/silver06_gatekeeper_checkpoint.json` | 702 | `cd008fb6f89bf2e3fa4b6a5e22acc0b83a384fb1edea1b55b22e267c78759693` | Kaggle 云端认证出厂 Checkpoint |
| `kaggle_trainer/trainer.py` | 5,955 | `6f03af9fafb206b4bb2d406e313ee4135d61d4d1ac65fa965a407385fc77281e` | Kaggle 云端真实训练与门禁测试脚本 |
| `requirements.txt` | 58 | `0a3119d29299608c3eaff95535563df71f2730f74f4f6a1d5345a13e5a938352` | 最小生产环境依赖声明 |
| `scripts/run_2yr_backtest.py` | 3,479 | `84429e821aa488153dd910b655ad3fbefb5745d6d12b520de5c059cd82aa6af1` | 2 年全周期回测主入口脚本 |
| `scripts/verify_reproduction.py` | 2,853 | `7265f27a5df86dfa12870937bd250c68ba8ce6939081dc4a37849aaf73415c6b` | 一键出厂门禁与记账断言验证脚本 |
