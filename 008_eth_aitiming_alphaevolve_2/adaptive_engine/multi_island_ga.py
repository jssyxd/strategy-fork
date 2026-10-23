"""
007 ETH AI 择时策略 - 升级版多岛屿自适应遗传演化引擎 (Multi-Island GA Engine)
解决缺陷4：早熟收敛与多样性枯竭
特性：
1. 5 个独立岛屿隔离演化，周期性优势个体环形迁移 (Ring Migration)
2. 柯西分布自适应大变异与灾变重启机制 (Cataclysmic Mutation & Restart)
3. 动态早停耐心机制 (Early Stopping Patience)
"""
import random
import numpy as np

class MultiIslandAlphaEvolveEngine:
    def __init__(self, num_islands=4, pop_per_island=8, migration_interval=30, 
                 cataclysm_patience=150, max_generations=150):
        self.num_islands = num_islands
        self.pop_per_island = pop_per_island
        self.migration_interval = migration_interval
        self.cataclysm_patience = cataclysm_patience
        self.max_generations = max_generations

    def init_individual(self):
        # 9 维染色体超参数
        return [
            random.uniform(0.82, 0.96), # gamma
            random.uniform(1.0, 3.0),   # w_imb
            random.uniform(0.5, 2.5),   # w_bo
            random.uniform(0.2, 1.5),   # w_dev
            random.uniform(0.5, 0.95),  # th_50
            random.uniform(1.0, 1.8),   # th_75
            random.uniform(1.2, 2.5),   # trail_mult
            random.uniform(2.0, 3.2),   # sl_mult
            random.uniform(1.2, 2.2)    # tp_mult
        ]

    def evolve(self, executor, features: dict, start_idx: int, end_idx: int):
        # 初始化 5 个岛屿种群
        islands = [[self.init_individual() for _ in range(self.pop_per_island)] for _ in range(self.num_islands)]
        
        global_best_fit = -999999.0
        global_best_g = None
        global_best_stats = None
        stagnant_gens = 0
        
        for gen in range(1, self.max_generations + 1):
            island_bests = []
            
            for island_id in range(self.num_islands):
                pop = islands[island_id]
                # 评估各岛个体
                evals = []
                for ind in pop:
                    fit, r, d, w, cnt, eq = executor.simulate(features, ind, start_idx, end_idx)
                    evals.append((fit, r, d, w, cnt, ind))
                    if fit > global_best_fit and cnt >= 10:
                        global_best_fit = fit
                        global_best_g = ind
                        global_best_stats = {'return': r, 'mdd': d, 'win_rate': w, 'trades': cnt}
                        stagnant_gens = 0
                
                evals.sort(key=lambda x: x[0], reverse=True)
                island_bests.append(evals[0][5])
                
                # 岛内产生新一代：Top 3 精英
                elites = [x[5] for x in evals[:3]]
                new_pop = list(elites)
                
                while len(new_pop) < self.pop_per_island:
                    p1, p2 = random.choice(elites), random.choice(elites)
                    # 均匀交叉
                    child = [p1[k] if random.random() > 0.5 else p2[k] for k in range(len(p1))]
                    # 变异：35% 几率发生轻微微调，10% 发生柯西大跳跃
                    if random.random() < 0.35:
                        idx = random.randint(0, len(child) - 1)
                        if random.random() < 0.20:
                            # 柯西重尾变异 (Cauchy Mutation) 帮助跳出局部极值
                            cauchy_step = np.random.standard_cauchy() * 0.2
                            child[idx] = max(0.01, child[idx] * (1.0 + cauchy_step))
                        else:
                            child[idx] *= random.uniform(0.85, 1.15)
                    new_pop.append(child)
                islands[island_id] = new_pop
                
            stagnant_gens += 1
            
            # 环形迁移 (Ring Migration)
            if gen % self.migration_interval == 0:
                for i in range(self.num_islands):
                    next_i = (i + 1) % self.num_islands
                    # 将本岛最优个体迁移至下一岛屿，替换其最差个体
                    islands[next_i][-1] = list(island_bests[i])

            # 灾变机制 (Cataclysmic Event)：若持续停滞，强制大洗牌
            if stagnant_gens >= self.cataclysm_patience:
                # 保留全局最优，其余所有岛屿重置变异
                for i in range(self.num_islands):
                    for j in range(1, self.pop_per_island):
                        base = list(global_best_g) if global_best_g else self.init_individual()
                        islands[i][j] = [v * random.uniform(0.5, 1.5) for v in base]
                stagnant_gens = 0

            # 早停检查：如果达到很高代数且性能优异且已收敛
            if gen > 800 and stagnant_gens > 400:
                break
                
        return global_best_g, global_best_fit, global_best_stats
