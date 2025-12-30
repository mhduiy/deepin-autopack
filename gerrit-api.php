<?php
// Gerrit API函数库 - 专门负责调用Gerrit接口并返回数据

require_once __DIR__ . '/../config/database.php';

// Gerrit认证信息
define('GERRIT_USERNAME', 'ut000190');
define('GERRIT_PASSWORD', 'abcd@123');
define('GERRIT_BASE_URL', 'https://gerrit.uniontech.com');

/**
 * 获取Gerrit用户认证信息
 * @param Database $db 数据库实例
 * @return array|null 包含username和password的数组，失败返回null
 */
function getGerritCredentials($db) {
    $user = $db->fetch("SELECT username, plain_password FROM users WHERE status = 1 LIMIT 1");
    
    if (!$user || empty($user['username']) || empty($user['plain_password'])) {
        error_log("No valid user credentials found for Gerrit API");
        return null;
    }
    
    return [
        'username' => $user['username'],
        'password' => $user['plain_password']
    ];
}

/**
 * 执行Gerrit API请求
 * @param string $url API URL
 * @param array $credentials 认证信息
 * @param array $options 请求选项
 * @return array 包含success、data、message的数组
 */
function executeGerritRequest($url, $credentials, $options = []) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, $options['timeout'] ?? 30);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    curl_setopt($ch, CURLOPT_USERPWD, "{$credentials['username']}:{$credentials['password']}");
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/json',
        'Accept: application/json'
    ]);
    curl_setopt($ch, CURLOPT_USERAGENT, 'Mozilla/5.0 (compatible; ProjectManager/1.0)');
    // 设置请求方法
    if (isset($options['method'])) {
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $options['method']);
    }
    
    // 设置POST数据
    if (isset($options['post_data'])) {
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $options['post_data']);
    }
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);

    if ($error) {
        return [
            'success' => false,
            'message' => 'Gerrit API请求失败: ' . $error,
            'data' => null
        ];
    }
    
    if ($httpCode !== 200) {
        return [
            'success' => false,
            'message' => "Gerrit API返回错误，HTTP状态码: {$httpCode}",
            'data' => null
        ];
    }
    
    // Gerrit API返回的数据前面有)]}'，需要去掉
    $response = preg_replace('/^\)\]\}\'/', '', $response);
    
    $gerritData = json_decode($response, true);
    
    if (json_last_error() !== JSON_ERROR_NONE) {
        return [
            'success' => false,
            'message' => 'Gerrit API响应格式错误',
            'data' => null
        ];
    }
    
    return [
        'success' => true,
        'message' => 'Gerrit API请求成功',
        'data' => $gerritData
    ];
}

/**
 * 根据commit获取分支信息
 * @param string $commit Commit哈希
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getBranchFromCommit($commit, $db) {
    if (!$commit) {
        return [
            'success' => false,
            'message' => 'Commit哈希不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    $gerritUrl = "https://gerrit.uniontech.com/a/changes/{$commit}";
    
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    $gerritData = $result['data'];
    $branch = $gerritData['branch'] ?? null;
    
    return [
        'success' => true,
        'message' => '成功获取分支信息',
        'data' => [
            'branch' => $branch,
            'change_info' => $gerritData
        ]
    ];
}

/**
 * 获取提交详情
 * @param string $commit Commit哈希
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getCommitDetail($commit, $db) {
    if (!$commit) {
        return [
            'success' => false,
            'message' => 'Commit哈希不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    $gerritUrl = "https://gerrit.uniontech.com/a/changes/{$commit}/detail";
    
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    return [
        'success' => true,
        'message' => '成功获取提交详情',
        'data' => $result['data']
    ];
}

/**
 * 获取项目信息
 * @param string $projectName 项目名称
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getProjectInfo($projectName, $db) {
    if (!$projectName) {
        return [
            'success' => false,
            'message' => '项目名称不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    $gerritUrl = "https://gerrit.uniontech.com/a/projects/" . urlencode($projectName);
    
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    return [
        'success' => true,
        'message' => '成功获取项目信息',
        'data' => $result['data']
    ];
}

/**
 * 获取项目分支列表
 * @param string $projectName 项目名称
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getProjectBranches($projectName, $db) {
    if (!$projectName) {
        return [
            'success' => false,
            'message' => '项目名称不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    $gerritUrl = "https://gerrit.uniontech.com/a/projects/" . urlencode($projectName) . "/branches/";
    
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    return [
        'success' => true,
        'message' => '成功获取项目分支列表',
        'data' => $result['data']
    ];
}

/**
 * 获取分支最新提交
 * @param string $projectName 项目名称
 * @param string $branchName 分支名称
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getBranchLatestCommit($projectName, $branchName, $db) {
    if (!$projectName || !$branchName) {
        return [
            'success' => false,
            'message' => '项目名称和分支名称不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    $gerritUrl = "https://gerrit.uniontech.com/a/projects/" . urlencode($projectName) . "/branches/" . urlencode($branchName);
    
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    return [
        'success' => true,
        'message' => '成功获取分支最新提交',
        'data' => $result['data']
    ];
}

/**
 * 搜索变更
 * @param array $queryParams 查询参数
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function searchChanges($queryParams, $db) {
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    $query = http_build_query($queryParams);
    $gerritUrl = "https://gerrit.uniontech.com/a/changes/?{$query}";
    
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    return [
        'success' => true,
        'message' => '成功搜索变更',
        'data' => $result['data']
    ];
}

/**
 * 获取变更详情
 * @param string $changeId 变更ID
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getChangeDetail($changeId, $db) {
    if (!$changeId) {
        return [
            'success' => false,
            'message' => '变更ID不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    $gerritUrl = "https://gerrit.uniontech.com/a/changes/{$changeId}/detail";
    
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    return [
        'success' => true,
        'message' => '成功获取变更详情',
        'data' => $result['data']
    ];
}

/**
 * 获取项目分支的最新提交
 * @param string $moduleName 模块名称
 * @param string $branchName 分支名称
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getProjectBranchLatestRevision($moduleName, $branchName, $db) {
    if (!$moduleName || !$branchName) {
        return [
            'success' => false,
            'message' => '模块名称和分支名称不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    $gerritUrl = "https://gerrit.uniontech.com/a/projects/" . urlencode($moduleName) . "/branches?m=" . urlencode($branchName);
    
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    $gerritData = $result['data'];
    
    // 查找匹配的分支
    $targetBranch = null;
    foreach ($gerritData as $branch) {
        if (isset($branch['ref']) && $branch['ref'] === "refs/heads/{$branchName}") {
            $targetBranch = $branch;
            break;
        }
    }
    
    if (!$targetBranch) {
        return [
            'success' => false,
            'message' => "未找到分支: {$branchName}",
            'data' => null
        ];
    }
    
    $revision = $targetBranch['revision'] ?? null;
    
    return [
        'success' => true,
        'message' => '成功获取项目分支最新提交',
        'data' => [
            'revision' => $revision,
            'branch_info' => $targetBranch
        ]
    ];
}

/**
 * 获取交付记录的提测信息
 * @param int $deliveryId 交付记录ID
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getDeliveryTestInfo($deliveryId, $db) {
    if (!$deliveryId) {
        return [
            'success' => false,
            'message' => '交付记录ID不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    // 获取交付记录基本信息
    $deliveryRecord = $db->fetch("
        SELECT 
            pdr.*,
            p.name as project_name
        FROM project_deliver_record pdr
        JOIN projects p ON pdr.project_id = p.id
        WHERE pdr.id = ?
    ", [$deliveryId]);
    
    if (!$deliveryRecord) {
        return [
            'success' => false,
            'message' => '交付记录不存在',
            'data' => null
        ];
    }
    
    // 获取交付打包信息
    $packageInfo = $db->fetchAll("
        SELECT 
            dp.*,
            m.name as module_name,
            m.repo_url,
            m.main_branch
        FROM deliver_package dp
        JOIN modules m ON dp.module_id = m.id
        WHERE dp.delivery_record_id = ?
        ORDER BY dp.updated_at DESC
    ", [$deliveryId]);
    
    $testInfo = [
        'delivery_id' => $deliveryId,
        'project_name' => $deliveryRecord['project_name'],
        'crp_id' => $deliveryRecord['crp_id'],
        'crp_name' => $deliveryRecord['crp_name'],
        'crp_state' => $deliveryRecord['crp_state'],
        'modules' => []
    ];
    
    // 为每个模块获取Gerrit提测信息
    foreach ($packageInfo as $package) {
        $moduleTestInfo = [
            'module_id' => $package['module_id'],
            'module_name' => $package['module_name'],
            'build_commit' => $package['build_commit'],
            'build_branch' => $package['build_branch'],
            'build_state' => $package['build_state'],
            'commit_detail' => null,
            'recent_commits' => null,
            'branch_info' => null
        ];
        
        // 如果有构建commit，获取详细信息
        if (!empty($package['build_commit'])) {
            $commitDetailResult = getCommitDetail($package['build_commit'], $db);
            if ($commitDetailResult['success']) {
                $moduleTestInfo['commit_detail'] = $commitDetailResult['data'];
            }
        }
        
        // 获取模块的最新提交信息
        if (!empty($package['repo_url'])) {
            // 从repo_url提取项目名称
            $projectName = extractProjectNameFromUrl($package['repo_url']);
            $branchName = $package['build_branch'] ?: $package['main_branch'];
            
            if ($projectName && $branchName) {
                // 获取分支最新提交
                $branchResult = getBranchLatestCommit($projectName, $branchName, $db);
                if ($branchResult['success']) {
                    $moduleTestInfo['branch_info'] = $branchResult['data'];
                }
                
                // 搜索该分支的最近提交（用于提测信息）
                $recentCommitsResult = searchChanges([
                    'q' => "project:{$projectName} branch:{$branchName} status:merged",
                    'n' => '10',  // 最近10个提交
                    'o' => 'CURRENT_REVISION'
                ], $db);
                
                if ($recentCommitsResult['success']) {
                    $moduleTestInfo['recent_commits'] = $recentCommitsResult['data'];
                }
            }
        }
        
        $testInfo['modules'][] = $moduleTestInfo;
    }
    
    return [
        'success' => true,
        'message' => '成功获取提测信息',
        'data' => $testInfo
    ];
}

/**
 * 从仓库URL中提取项目名称
 * @param string $repoUrl 仓库URL
 * @return string|null 项目名称
 */
function extractProjectNameFromUrl($repoUrl) {
    if (empty($repoUrl)) {
        return null;
    }
    
    // 处理Gerrit URL格式：https://gerrit.uniontech.com/plugins/gitiles//project-name
    if (preg_match('/gerrit\.uniontech\.com\/plugins\/gitiles\/+(.+?)(?:\/|$)/', $repoUrl, $matches)) {
        return trim($matches[1], '/');
    }
    
    // 处理标准Git URL格式：https://gerrit.uniontech.com/project-name.git
    if (preg_match('/gerrit\.uniontech\.com\/([^\/]+?)(?:\.git)?(?:\/|$)/', $repoUrl, $matches)) {
        return $matches[1];
    }
    
    // 处理其他格式
    $parsed = parse_url($repoUrl);
    if (isset($parsed['path'])) {
        $path = trim($parsed['path'], '/');
        $path = preg_replace('/\.git$/', '', $path);
        return $path;
    }
    
    return null;
}

/**
 * 获取模块的构建和测试状态
 * @param int $moduleId 模块ID
 * @param string $branchName 分支名称
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getModuleBuildTestStatus($moduleId, $branchName, $db) {
    if (!$moduleId) {
        return [
            'success' => false,
            'message' => '模块ID不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    // 获取模块信息
    $module = $db->fetch("SELECT * FROM modules WHERE id = ?", [$moduleId]);
    if (!$module) {
        return [
            'success' => false,
            'message' => '模块不存在',
            'data' => null
        ];
    }
    
    $projectName = extractProjectNameFromUrl($module['repo_url']);
    $targetBranch = $branchName ?: $module['main_branch'];
    
    if (!$projectName) {
        return [
            'success' => false,
            'message' => '无法从仓库URL提取项目名称',
            'data' => null
        ];
    }
    
    $buildTestStatus = [
        'module_name' => $module['name'],
        'project_name' => $projectName,
        'branch' => $targetBranch,
        'latest_commit' => null,
        'build_status' => 'unknown',
        'test_results' => []
    ];
    
    // 获取最新提交
    $latestCommitResult = getBranchLatestCommit($projectName, $targetBranch, $db);
    if ($latestCommitResult['success']) {
        $buildTestStatus['latest_commit'] = $latestCommitResult['data'];
    }
    
    // 搜索带有构建/测试信息的提交
    $changesResult = searchChanges([
        'q' => "project:{$projectName} branch:{$targetBranch} status:merged",
        'n' => '5',
        'o' => 'CURRENT_REVISION,MESSAGES'
    ], $db);
    
    if ($changesResult['success']) {
        $buildTestStatus['test_results'] = $changesResult['data'];
    }
    
    return [
        'success' => true,
        'message' => '成功获取构建测试状态',
        'data' => $buildTestStatus
    ];
}

/**
 * 获取单个commit的详细信息
 * @param string $commitHash 完整的commit哈希
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getCommitInfo($moduleName, $commitHash, $db) {
    try {
        // 获取Gerrit认证信息
        $credentials = getGerritCredentials($db);
        if (!$credentials) {
            return [
                'success' => false,
                'message' => '无法获取Gerrit认证信息',
                'data' => null
            ];
        }
        
        // 构建API URL - 使用commit前6位作为revision
        $revision = substr($commitHash, 0, 6);
        // $url = "https://gerrit.uniontech.com/a/changes/{$commitHash}/revisions/{$revision}/commit";
        $url = "https://gerrit.uniontech.com/a/projects/".urlencode($moduleName)."/commits/{$commitHash}";
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_USERPWD, "{$credentials['username']}:{$credentials['password']}");
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json',
            'Accept: application/json'
        ]);
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        if ($response === false || $httpCode !== 200) {
            error_log("Gerrit commit API失败: HTTP {$httpCode}, URL: {$url}");
            return [
                'success' => false,
                'message' => "获取commit信息失败: HTTP {$httpCode}",
                'data' => null
            ];
        }
        
        // 移除Gerrit API的前缀
        $cleanResponse = preg_replace('/^\)\]\}\'/', '', $response);
        $commitData = json_decode($cleanResponse, true);
        
        if (json_last_error() !== JSON_ERROR_NONE) {
            error_log("Gerrit commit响应JSON解析错误: " . json_last_error_msg());
            return [
                'success' => false,
                'message' => 'commit响应格式错误',
                'data' => null
            ];
        }
        
        return [
            'success' => true,
            'message' => '成功获取commit信息',
            'data' => $commitData
        ];
        
    } catch (Exception $e) {
        error_log("获取commit信息异常: " . $e->getMessage());
        return [
            'success' => false,
            'message' => '获取commit信息异常: ' . $e->getMessage(),
            'data' => null
        ];
    }
}

/**
 * 递归获取从build_commit到base_commit之间的所有提交信息
 * @param string $currentCommit 当前commit哈希
 * @param string $baseCommit 基础commit哈希(停止条件)
 * @param Database $db 数据库实例
 * @param array $result 收集的结果(递归用)
 * @return array 包含success、data、message的数组
 */
function getCommitHistory($moduleName, $currentCommit, $baseCommit, $db, $result = []) {
    try {
        // 如果当前commit等于base_commit，停止递归
        if ($currentCommit === $baseCommit) {
            return [
                'success' => true,
                'message' => '成功获取提交历史',
                'data' => $result
            ];
        }
        
        // 获取当前commit信息
        $commitResult = getCommitInfo($moduleName, $currentCommit, $db);
        if (!$commitResult['success']) {
            return $commitResult;
        }
        
        $commitData = $commitResult['data'];
        
        // 解析commit message获取PMS信息
        $pmsInfo = parseCommitMessage($commitData['message'] ?? '');
        
        // 添加到结果中
        $result[] = [
            'commit' => $currentCommit,
            'author' => $commitData['author']['name'] ?? '',
            'message' => $commitData['message'] ?? '',
            'pms_url' => $pmsInfo['pms_url'],
            'influence' => $pmsInfo['influence'],
            'parents' => $commitData['parents'] ?? []
        ];
        
        // 检查parents
        $parents = $commitData['parents'] ?? [];
        if (empty($parents)) {
            // 没有父提交，结束递归
            return [
                'success' => true,
                'message' => '成功获取提交历史',
                'data' => $result
            ];
        }
        
        // 检查第一个parent是否等于base_commit
        $firstParent = $parents[0]['commit'] ?? '';
        if ($firstParent === $baseCommit) {
            // 找到base_commit，结束递归
            return [
                'success' => true,
                'message' => '成功获取提交历史',
                'data' => $result
            ];
        }
        
        // 继续递归查询第一个parent
        if (!empty($firstParent)) {
            return getCommitHistory($moduleName, $firstParent, $baseCommit, $db, $result);
        }
        
        // 没有有效的parent，结束递归
        return [
            'success' => true,
            'message' => '成功获取提交历史',
            'data' => $result
        ];
        
    } catch (Exception $e) {
        error_log("获取提交历史异常: " . $e->getMessage());
        return [
            'success' => false,
            'message' => '获取提交历史异常: ' . $e->getMessage(),
            'data' => null
        ];
    }
}

/**
 * 解析commit message获取PMS链接和影响范围
 * @param string $message commit消息
 * @return array 包含pms_url和influence的数组
 */
function parseCommitMessage($message) {
    $result = [
        'pms_url' => null,
        'influence' => null
    ];
    
    if (empty($message)) {
        return $result;
    }
    
    // 匹配bug或task链接
    // 常见格式：Bug: https://pms.uniontech.com/bug-view-xxx.html
    //          Task: https://pms.uniontech.com/task-view-xxx.html
    if (preg_match('/(?:Bug|Task):\s*(https?:\/\/[^\s]+)/i', $message, $matches)) {
        $result['pms_url'] = $matches[1];
    } else {
        // 匹配PMS链接
        // 常见格式：PMS: BUG-xxx， PMS: TASK-xxx
        if (preg_match('/PMS:\s*(BUG|TASK)-(\d+)/i', $message, $matches)) {
            $result['pms_url'] = 'https://pms.uniontech.com/' . $matches[1] . '-view-' . $matches[2] . '.html';
        }
    }
    
    // 匹配Influence后面的内容
    // 格式：Influence: 一些影响描述
    if (preg_match('/Influence:\s*(.+?)(?:\n|$)/i', $message, $matches)) {
        $influence = trim($matches[1]);
        if (!empty($influence)) {
            $result['influence'] = $influence;
        }
    }
    
    // 如果Influence为空，尝试匹配Log字段
    if (empty($result['influence'])) {
        if (preg_match('/Log:\s*(.+?)(?:\n|$)/i', $message, $matches)) {
            $log = trim($matches[1]);
            if (!empty($log)) {
                $result['influence'] = $log;
            }
        }
    }
    
    // 如果Log也为空，使用message的第一行
    if (empty($result['influence'])) {
        $lines = explode("\n", trim($message));
        if (!empty($lines[0])) {
            $firstLine = trim($lines[0]);
            if (!empty($firstLine)) {
                $result['influence'] = $firstLine;
            }
        }
    }
    
    return $result;
}

/**
 * 生成交付记录的PMS信息
 * @param int $deliveryRecordId 交付记录ID
 * @param Database $db 数据库实例
 * @return array 包含success、message的数组
 */
function generateDeliveryPmsInfo($deliveryRecordId, $db) {
    try {
        // 先清理当前交付记录对应的提测记录
        $db->execute("DELETE FROM deliver_pms WHERE deliver_id = ?", [$deliveryRecordId]);
        
        // 获取当前交付记录的打包信息
        $packageInfo = $db->fetchAll("
            SELECT 
                dp.*,
                m.name as module_name,
                m.repo_url
            FROM deliver_package dp
            LEFT JOIN modules m ON dp.module_id = m.id
            WHERE dp.delivery_record_id = ?
            ORDER BY dp.created_at ASC
        ", [$deliveryRecordId]);
        
        if (empty($packageInfo)) {
            return [
                'success' => false,
                'message' => '没有找到打包信息'
            ];
        }
        
        $totalInserted = 0;
        
        foreach ($packageInfo as $package) {
            $moduleId = $package['module_id'];
            $baseCommit = $package['base_commit'];
            $buildCommit = $package['build_commit'];
            $moduleName = $package['module_name'];
            
            // 检查必要字段：base_commit 或 build_commit 为空则跳过
            if (empty($buildCommit) || empty($baseCommit)) {
                error_log("模块 {$package['build_module_name']} 的 base_commit 或 build_commit 为空，跳过");
                continue;
            }
            
            // 如果base_commit等于build_commit，跳过处理
            if ($baseCommit === $buildCommit) {
                error_log("模块 {$package['build_module_name']} 的 base_commit 等于 build_commit，跳过");
                continue;
            }
            
            // 获取从build_commit到base_commit的提交历史
            $historyResult = getCommitHistory($moduleName, $buildCommit, $baseCommit, $db);
            if ($historyResult['success']) {
                $commits = $historyResult['data'];
                
                foreach ($commits as $commitInfo) {
                    $db->execute("
                        INSERT INTO deliver_pms (deliver_id, module_id, commit_hash, pms_url, influence, author, message)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ", [
                        $deliveryRecordId,
                        $moduleId,
                        $commitInfo['commit'],
                        $commitInfo['pms_url'],
                        $commitInfo['influence'],
                        $commitInfo['author'],
                        $commitInfo['message']
                    ]);
                    $totalInserted++;
                }
            }
        }
        
        return [
            'success' => true,
            'message' => "成功生成PMS信息，共插入 {$totalInserted} 条记录"
        ];
        
    } catch (Exception $e) {
        error_log("生成交付PMS信息异常: " . $e->getMessage());
        return [
            'success' => false,
            'message' => '生成PMS信息异常: ' . $e->getMessage()
        ];
    }
}

/**
 * 重新生成交付记录的PMS信息（支持模块级别）
 * @param int $deliveryRecordId 交付记录ID
 * @param int|null $moduleId 模块ID，如果为null则重新生成所有模块
 * @param Database $db 数据库实例
 * @return array
 */
function regenerateDeliveryPmsInfo($deliveryRecordId, $moduleId = null, $db) {
    try {
        if ($moduleId) {
            // 清理特定模块的提测记录
            $db->execute("DELETE FROM deliver_pms WHERE deliver_id = ? AND module_id = ?", [$deliveryRecordId, $moduleId]);
            
            // 获取特定模块的打包信息
            $packageInfo = $db->fetchAll("
                SELECT 
                    dp.*,
                    m.name as module_name,
                    m.repo_url
                FROM deliver_package dp
                LEFT JOIN modules m ON dp.module_id = m.id
                WHERE dp.delivery_record_id = ? AND dp.module_id = ?
                ORDER BY dp.created_at ASC
            ", [$deliveryRecordId, $moduleId]);
            
            $message = '模块PMS信息重新生成完成';
        } else {
            // 清理当前交付记录对应的所有提测记录
            $db->execute("DELETE FROM deliver_pms WHERE deliver_id = ?", [$deliveryRecordId]);
            
            // 获取当前交付记录的所有打包信息
            $packageInfo = $db->fetchAll("
                SELECT 
                    dp.*,
                    m.name as module_name,
                    m.repo_url
                FROM deliver_package dp
                LEFT JOIN modules m ON dp.module_id = m.id
                WHERE dp.delivery_record_id = ?
                ORDER BY dp.created_at ASC
            ", [$deliveryRecordId]);
            
            $message = '所有PMS信息重新生成完成';
        }
        
        if (empty($packageInfo)) {
            return [
                'success' => false,
                'message' => '没有找到对应的打包信息'
            ];
        }
        
        $totalInserted = 0;
        
        foreach ($packageInfo as $package) {
            $currentModuleId = $package['module_id'];
            $baseCommit = $package['base_commit'];
            $buildCommit = $package['build_commit'];
            $moduleName = $package['module_name'];
            
            // 检查必要字段：base_commit 或 build_commit 为空则跳过
            if (empty($buildCommit) || empty($baseCommit)) {
                error_log("模块 {$package['build_module_name']} 的 base_commit 或 build_commit 为空，跳过");
                continue;
            }
            
            // 如果base_commit等于build_commit，跳过处理
            if ($baseCommit === $buildCommit) {
                error_log("模块 {$package['build_module_name']} 的 base_commit 等于 build_commit，跳过");
                continue;
            }
            
            // 获取从build_commit到base_commit的提交历史
            $historyResult = getCommitHistory($moduleName, $buildCommit, $baseCommit, $db);
            if ($historyResult['success']) {
                $commits = $historyResult['data'];
                
                foreach ($commits as $commitInfo) {
                    $db->execute("
                        INSERT INTO deliver_pms (deliver_id, module_id, commit_hash, pms_url, influence, author, message)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ", [
                        $deliveryRecordId,
                        $currentModuleId,
                        $commitInfo['commit'],
                        $commitInfo['pms_url'],
                        $commitInfo['influence'],
                        $commitInfo['author'],
                        $commitInfo['message']
                    ]);
                    $totalInserted++;
                }
            }
        }
        
        return [
            'success' => true,
            'message' => "{$message}，共插入 {$totalInserted} 条记录"
        ];
        
    } catch (Exception $e) {
        error_log("重新生成交付PMS信息异常: " . $e->getMessage());
        return [
            'success' => false,
            'message' => '重新生成PMS信息异常: ' . $e->getMessage()
        ];
    }
}

/**
 * 添加PMS链接到交付记录
 * @param int $deliveryId 交付记录ID
 * @param array $pmsLinks PMS链接数组
 * @param Database $db 数据库实例
 * @return array
 */
function addPmsLinksToDelivery($deliveryId, $pmsLinks, $db) {
    try {
        $addedCount = 0;
        $errors = [];
        
        foreach ($pmsLinks as $pmsUrl) {
            $pmsUrl = trim($pmsUrl);
            
            // 验证URL格式
            if (!filter_var($pmsUrl, FILTER_VALIDATE_URL)) {
                $errors[] = "无效的URL格式: {$pmsUrl}";
                continue;
            }
            
            // 检查是否已存在相同的PMS链接
            $existing = $db->fetch("
                SELECT id FROM deliver_pms 
                WHERE deliver_id = ? AND pms_url = ?
            ", [$deliveryId, $pmsUrl]);
            
            if ($existing) {
                $errors[] = "PMS链接已存在: {$pmsUrl}";
                continue;
            }
            
            // 解析PMS链接信息
            $pmsInfo = parsePmsUrl($pmsUrl);
            
            // 插入新的PMS记录
            $success = $db->execute("
                INSERT INTO deliver_pms (deliver_id, pms_url, type, influence, author, message)
                VALUES (?, ?, ?, ?, ?, ?)
            ", [
                $deliveryId,
                $pmsUrl,
                $pmsInfo['type'],
                $pmsInfo['influence'],
                $pmsInfo['author'],
                $pmsInfo['message']
            ]);
            
            if ($success) {
                $addedCount++;
            } else {
                $errors[] = "插入失败: {$pmsUrl}";
            }
        }
        
        $message = "成功添加 {$addedCount} 个转测单";
        if (!empty($errors)) {
            $message .= "，" . count($errors) . " 个失败";
        }
        
        return [
            'success' => true,
            'message' => $message,
            'added_count' => $addedCount,
            'errors' => $errors
        ];
        
    } catch (Exception $e) {
        error_log("添加PMS链接异常: " . $e->getMessage());
        return [
            'success' => false,
            'message' => '添加PMS链接异常: ' . $e->getMessage()
        ];
    }
}

/**
 * 解析PMS URL获取基本信息
 * @param string $pmsUrl PMS链接
 * @return array 包含type、influence、author、message的数组
 */
function parsePmsUrl($pmsUrl) {
    $result = [
        'type' => null,
        'influence' => null,
        'author' => null,
        'message' => null
    ];
    
    if (empty($pmsUrl)) {
        return $result;
    }
    
    // 从URL中判断类型
    if (preg_match('/bug-view/i', $pmsUrl)) {
        $result['type'] = 'Bug';
    } elseif (preg_match('/task-view/i', $pmsUrl)) {
        $result['type'] = 'Task';
    }
    
    $result['influence'] = "手动添加的转测单";
    
    return $result;
}

/**
 * 调用协作平台API获取BUG或Task详细信息
 * @param array $ids BUG或Task的ID数组
 * @param string $type 类型：'bug' 或 'task'
 * @return array
 */
function fetchCooperationData($ids, $type) {
    if (empty($ids)) {
        return [];
    }
    
    try {
        $idsString = implode(',', $ids);
        
        // 根据类型设置不同的controlId和worksheetId
        if ($type === 'bug') {
            $controlId = 'bugnum';
            $worksheetId = 'BUG_LIST';
        } else {
            $controlId = '639187a9a91e575a300be3a6';
            $worksheetId = 'TASK_LIST';
        }
        
        $requestData = [
            'appKey' => 'f7b8e6816d39a931',
            'sign' => 'ODlkNTVhNDdjZDhjNmYwODhjYjExZTU4NGFmODFkZDQzZjRlNGMzMzJlODdhNzhmNTVjYmQ4ZTA1MzAzNzc3Mw==',
            'worksheetId' => $worksheetId,
            'viewId' => '', // 添加viewId字段
            'pageSize' => 50,
            'pageIndex' => 1,
            'listType' => 0,
            'controls' => [],
            'filters' => [
                [
                    'controlId' => $controlId,
                    'dataType' => 2,
                    'spliceType' => 2,
                    'filterType' => 2,
                    'value' => $idsString
                ]
            ]
        ];
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, 'https://cooperation.uniontech.com/api/v2/open/worksheet/getFilterRows');
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($requestData));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json'
        ]);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curlError = curl_error($ch);
        curl_close($ch);
        
        // 增强日志记录
        error_log("协作平台API调用 - 类型: {$type}, worksheetId: {$worksheetId}, controlId: {$controlId}, IDs: {$idsString}");
        error_log("协作平台API响应 - HTTP状态码: {$httpCode}, 响应长度: " . strlen($response));
        
        if ($curlError) {
            error_log("协作平台API网络错误: {$curlError}");
            return [];
        }
        
        if ($httpCode !== 200) {
            error_log("协作平台API请求失败，HTTP状态码: {$httpCode}, 响应: " . substr($response, 0, 500));
            return [];
        }
        
        $data = json_decode($response, true);
        if (!$data || !isset($data['data']['rows'])) {
            error_log("协作平台API响应格式错误，响应内容: " . substr($response, 0, 1000));
            return [];
        }
        
        error_log("协作平台API成功解析，获取到 " . count($data['data']['rows']) . " 条记录");
        
        $result = [];
        foreach ($data['data']['rows'] as $index => $row) {
            if ($type === 'bug') {
                $id = $row['bugnum'] ?? '';
                $title = $row['bugtitle'] ?? '';
                $level = $row['630c6acfcf74a8b0029e7f33'] ?? '';
            } else {
                $id = $row['639187a9a91e575a300be3a6'] ?? '';
                $title = $row['bugtitle'] ?? '';
                $level = '【】';
            }
            
            if ($id) {
                $result[$id] = [
                    'title' => $title,
                    'level' => $level
                ];
                error_log("解析{$type}记录: ID={$id}, 标题=" . substr($title, 0, 50) . ", 级别={$level}");
            }
        }
        
        return $result;
        
    } catch (Exception $e) {
        error_log("调用协作平台API异常: " . $e->getMessage());
        return [];
    }
}

/**
 * 从PMS URL中提取ID和类型
 * @param string $url PMS URL
 * @return array ['id' => string, 'type' => string] 或 null
 */
function extractPmsInfo($url) {
    if (empty($url)) {
        return null;
    }
    
    // 匹配 bug-view-ID.html 或 task-view-ID.html
    if (preg_match('/\/(bug|task)-view-(\d+)\.html/', $url, $matches)) {
        return [
            'type' => $matches[1],
            'id' => $matches[2]
        ];
    }
    
    return null;
}

/**
 * 导出提测单Excel
 * @param int $deliveryId 交付记录ID
 * @param Database $db 数据库实例
 * @return array
 */
function exportTestInfoExcel($deliveryId, $db) {
    try {
        // 获取交付记录信息
        $deliveryRecord = $db->fetch("
            SELECT 
                pdr.*,
                p.name as project_name
            FROM project_deliver_record pdr
            JOIN projects p ON pdr.project_id = p.id
            WHERE pdr.id = ?
        ", [$deliveryId]);
        
        if (!$deliveryRecord) {
            return [
                'success' => false,
                'message' => '交付记录不存在'
            ];
        }
        
        // 获取打包信息
        $packageInfo = $db->fetchAll("
            SELECT 
                dp.*,
                m.name as module_name
            FROM deliver_package dp
            LEFT JOIN modules m ON dp.module_id = m.id
            WHERE dp.delivery_record_id = ?
            ORDER BY dp.created_at ASC
        ", [$deliveryId]);
        
        // 获取提测信息
        $pmsData = $db->fetchAll("
            SELECT 
                dp.*,
                m.name as module_name
            FROM deliver_pms dp
            LEFT JOIN modules m ON dp.module_id = m.id
            WHERE dp.deliver_id = ?
            ORDER BY dp.created_at DESC
        ", [$deliveryId]);
        
        // 丰富PMS数据：调用协作平台API获取详细信息
        if (!empty($pmsData)) {
            $bugIds = [];
            $taskIds = [];
            $pmsUrlMap = []; // URL到数组索引的映射
            
            // 从PMS URL中提取ID和类型
            foreach ($pmsData as $index => $pms) {
                $pmsInfo = extractPmsInfo($pms['pms_url']);
                if ($pmsInfo) {
                    if ($pmsInfo['type'] === 'bug') {
                        $bugIds[] = $pmsInfo['id'];
                    } else {
                        $taskIds[] = $pmsInfo['id'];
                    }
                    $pmsUrlMap[$pms['pms_url']] = $index;
                }
            }
            
            // 批量获取BUG详细信息
            if (!empty($bugIds)) {
                $bugDetails = fetchCooperationData($bugIds, 'bug');
                foreach ($pmsData as $index => &$pms) {
                    $pmsInfo = extractPmsInfo($pms['pms_url']);
                    if ($pmsInfo && $pmsInfo['type'] === 'bug') {
                        $bugId = $pmsInfo['id'];
                        if (isset($bugDetails[$bugId])) {
                            $pms['cooperation_title'] = $bugDetails[$bugId]['title'];
                            $pms['cooperation_level'] = $bugDetails[$bugId]['level'];
                        }
                    }
                }
            }
            
            // 批量获取Task详细信息
            if (!empty($taskIds)) {
                $taskDetails = fetchCooperationData($taskIds, 'task');
                foreach ($pmsData as $index => &$pms) {
                    $pmsInfo = extractPmsInfo($pms['pms_url']);
                    if ($pmsInfo && $pmsInfo['type'] === 'task') {
                        $taskId = $pmsInfo['id'];
                        if (isset($taskDetails[$taskId])) {
                            $pms['cooperation_title'] = $taskDetails[$taskId]['title'];
                            $pms['cooperation_level'] = $taskDetails[$taskId]['level'];
                        }
                    }
                }
            }
            
            error_log("PMS数据丰富完成，BUG数量: " . count($bugIds) . ", Task数量: " . count($taskIds));
        }
        
        // 直接生成Excel文件（不使用模板）
        $tempPath = sys_get_temp_dir() . '/test_info_' . $deliveryId . '_' . time() . '.xlsx';
        $result = generateExcelDirectly($tempPath, $deliveryRecord, $packageInfo, $pmsData);
        
        if (!$result) {
            return [
                'success' => false,
                'message' => 'Excel文件生成失败'
            ];
        }
        
        // 构建时间+主题名称的文件名
        $currentTime = date('Y-m-d');
        $topicName = $deliveryRecord['crp_name'] ?? $deliveryRecord['project_name'] ?? "未知主题";
        
        // 清理主题名称，去掉文件名不支持的字符
        $cleanTopicName = preg_replace('/[<>:"\/\\|?*]/', '-', $topicName);
        $cleanTopicName = trim($cleanTopicName);
        
        $filename = "{$currentTime} {$cleanTopicName}.xlsx";
        
        return [
            'success' => true,
            'filepath' => $tempPath,
            'filename' => $filename
        ];
        
    } catch (Exception $e) {
        error_log("导出提测单Excel异常: " . $e->getMessage());
        return [
            'success' => false,
            'message' => '导出异常: ' . $e->getMessage()
        ];
    }
}

/**
 * 基于模板生成Excel文件 - 真正填充数据到模板
 * @param string $templatePath 模板文件路径
 * @param string $outputPath 输出文件路径
 * @param array $deliveryRecord 交付记录信息
 * @param array $packageInfo 打包信息
 * @param array $pmsData 提测信息
 * @return bool
 */
function generateExcelFromTemplate($templatePath, $outputPath, $deliveryRecord, $packageInfo, $pmsData) {
    try {
        // 检查模板文件是否存在
        if (!file_exists($templatePath)) {
            error_log("模板文件不存在: $templatePath");
            return false;
        }
        
        // 检查模板文件格式
        $pathInfo = pathinfo($templatePath);
        $extension = strtolower($pathInfo['extension']);
        
        if ($extension === 'xls') {
            // .xls 文件：直接复制模板（二进制格式，难以修改）
            if (!copy($templatePath, $outputPath)) {
                error_log("无法复制.xls模板文件: $templatePath");
                return false;
            }
            error_log("成功复制.xls模板文件，建议用户手动填充数据");
            return true;
            
        } elseif ($extension === 'xlsx') {
            // .xlsx 文件：可以解压和修改
            return processXlsxTemplate($templatePath, $outputPath, $deliveryRecord, $packageInfo, $pmsData);
        } else {
            error_log("不支持的文件格式: $extension");
            return false;
        }
        
    } catch (Exception $e) {
        error_log("处理模板异常: " . $e->getMessage());
        return false;
    }
}

/**
 * 处理 .xlsx 格式的模板文件
 */
function processXlsxTemplate($templatePath, $outputPath, $deliveryRecord, $packageInfo, $pmsData) {
    try {
        // 复制模板文件
        if (!copy($templatePath, $outputPath)) {
            error_log("无法复制.xlsx模板文件: $templatePath");
            return false;
        }
        
        // 创建临时目录解压Excel
        $tempDir = sys_get_temp_dir() . '/excel_' . time() . '_' . rand(1000, 9999);
        if (!mkdir($tempDir)) {
            error_log("无法创建临时目录");
            return true; // 至少返回原模板
        }
        
        // 解压Excel文件
        $zip = new ZipArchive();
        if ($zip->open($outputPath) !== TRUE) {
            error_log("无法解压Excel文件，返回原模板");
            rmdir($tempDir);
            return true; // 至少返回原模板
        }
        
        $zip->extractTo($tempDir);
        $zip->close();
        
        // 准备填充数据
        $projectInfo = sprintf(
            "分支：%s，主题：%s，CRP地址：%s",
            $deliveryRecord['project_branch'] ?? '-',
            $deliveryRecord['crp_name'] ?? '-',
            $deliveryRecord['crp_addr'] ?? '-'
        );
        
        $success = false;
        
        // 尝试填充第一个工作表的6B单元格
        $sheet1Path = $tempDir . '/xl/worksheets/sheet1.xml';
        if (file_exists($sheet1Path)) {
            $content = file_get_contents($sheet1Path);
            if ($content !== false) {
                // 在B6单元格位置插入项目信息
                $newContent = fillCellB6($content, $projectInfo);
                if ($newContent && file_put_contents($sheet1Path, $newContent)) {
                    $success = true;
                    error_log("成功填充项目信息到B6单元格");
                }
            }
        }
        
        // 尝试填充第二个工作表的数据
        $sheet2Path = $tempDir . '/xl/worksheets/sheet2.xml';
        if (file_exists($sheet2Path)) {
            $content = file_get_contents($sheet2Path);
            if ($content !== false) {
                // 填充打包信息和提测信息
                $newContent = fillChangeLogData($content, $packageInfo, $pmsData);
                if ($newContent && file_put_contents($sheet2Path, $newContent)) {
                    $success = true;
                    error_log("成功填充ChangeLog数据");
                }
            }
        }
        
        if ($success) {
            // 重新打包Excel文件
            $newZip = new ZipArchive();
            if ($newZip->open($outputPath, ZipArchive::OVERWRITE) === TRUE) {
                $files = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($tempDir), RecursiveIteratorIterator::LEAVES_ONLY);
                foreach ($files as $file) {
                    if (!$file->isDir()) {
                        $filePath = $file->getRealPath();
                        $relativePath = substr($filePath, strlen($tempDir) + 1);
                        $relativePath = str_replace('\\', '/', $relativePath);
                        $newZip->addFile($filePath, $relativePath);
                    }
                }
                $newZip->close();
                error_log("成功重新打包Excel文件");
            }
        }
        
        // 清理临时目录
        deleteDirectory($tempDir);
        
        return true;
        
    } catch (Exception $e) {
        error_log("处理.xlsx模板异常: " . $e->getMessage());
        if (isset($tempDir) && is_dir($tempDir)) {
            deleteDirectory($tempDir);
        }
        return true; // 即使失败也返回原模板
    }
}

/**
 * 填充B6单元格数据
 */
function fillCellB6($xmlContent, $projectInfo) {
    try {
        // 查找B6单元格或在第6行插入B列数据
        $pattern = '/<row r="6"[^>]*>(.*?)<\/row>/s';
        if (preg_match($pattern, $xmlContent, $matches)) {
            // 第6行存在，在其中添加B列单元格
            $rowContent = $matches[1];
            $newCell = '<c r="B6" t="inlineStr"><is><t>' . htmlspecialchars($projectInfo, ENT_XML1) . '</t></is></c>';
            
            // 检查是否已有B6单元格
            if (strpos($rowContent, 'r="B6"') === false) {
                // 没有B6单元格，添加一个
                $newRowContent = $rowContent . $newCell;
                $newRow = '<row r="6"' . substr($matches[0], 8, strpos($matches[0], '>') - 8) . '>' . $newRowContent . '</row>';
                return str_replace($matches[0], $newRow, $xmlContent);
            } else {
                // 已有B6单元格，替换其内容
                $pattern = '/<c r="B6"[^>]*>.*?<\/c>/s';
                $newRowContent = preg_replace($pattern, $newCell, $rowContent);
                $newRow = '<row r="6"' . substr($matches[0], 8, strpos($matches[0], '>') - 8) . '>' . $newRowContent . '</row>';
                return str_replace($matches[0], $newRow, $xmlContent);
            }
        } else {
            // 第6行不存在，创建第6行和B6单元格
            $newRow = '<row r="6"><c r="B6" t="inlineStr"><is><t>' . htmlspecialchars($projectInfo, ENT_XML1) . '</t></is></c></row>';
            
            // 找到合适的位置插入
            $pattern = '/<\/sheetData>/';
            return preg_replace($pattern, $newRow . '</sheetData>', $xmlContent);
        }
    } catch (Exception $e) {
        error_log("填充B6单元格异常: " . $e->getMessage());
        return false;
    }
}

/**
 * 填充ChangeLog数据
 */
function fillChangeLogData($xmlContent, $packageInfo, $pmsData) {
    try {
        $newRows = '';
        $rowIndex = 2; // 从第2行开始填充
        
        // 填充打包信息
        foreach ($packageInfo as $package) {
            $moduleName = htmlspecialchars($package['module_name'] ?? $package['build_module_name'] ?? '-', ENT_XML1);
            $currentVersion = htmlspecialchars($package['cur_tag'] ?? '-', ENT_XML1);
            $buildCommit = htmlspecialchars($package['build_commit'] ?? '-', ENT_XML1);
            
            $newRows .= '<row r="' . $rowIndex . '">';
            $newRows .= '<c r="A' . $rowIndex . '" t="inlineStr"><is><t>' . $moduleName . '</t></is></c>';
            $newRows .= '<c r="B' . $rowIndex . '" t="inlineStr"><is><t>' . $moduleName . '</t></is></c>';
            $newRows .= '<c r="C' . $rowIndex . '" t="inlineStr"><is><t>' . $currentVersion . '</t></is></c>';
            $newRows .= '<c r="D' . $rowIndex . '" t="inlineStr"><is><t>' . $buildCommit . '</t></is></c>';
            $newRows .= '<c r="I' . $rowIndex . '" t="inlineStr"><is><t>否</t></is></c>';
            $newRows .= '<c r="M' . $rowIndex . '" t="inlineStr"><is><t>通过</t></is></c>';
            $newRows .= '</row>';
            
            $rowIndex++;
        }
        
        // 填充提测信息
        $processedPmsUrls = [];
        foreach ($pmsData as $pms) {
            $pmsUrl = $pms['pms_url'] ?? '';
            if (!empty($pmsUrl) && !isset($processedPmsUrls[$pmsUrl])) {
                $processedPmsUrls[$pmsUrl] = true;
                
                $author = htmlspecialchars($pms['author'] ?? '-', ENT_XML1);
                $influence = htmlspecialchars($pms['influence'] ?? '-', ENT_XML1);
                $pmsUrlEscaped = htmlspecialchars($pmsUrl, ENT_XML1);
                
                $newRows .= '<row r="' . $rowIndex . '">';
                $newRows .= '<c r="F' . $rowIndex . '" t="inlineStr"><is><t>' . $pmsUrlEscaped . '</t></is></c>';
                $newRows .= '<c r="I' . $rowIndex . '" t="inlineStr"><is><t>否</t></is></c>';
                $newRows .= '<c r="J' . $rowIndex . '" t="inlineStr"><is><t>' . $influence . '</t></is></c>';
                $newRows .= '<c r="K' . $rowIndex . '" t="inlineStr"><is><t>' . $author . '</t></is></c>';
                $newRows .= '<c r="L' . $rowIndex . '" t="inlineStr"><is><t>' . $author . '</t></is></c>';
                $newRows .= '<c r="M' . $rowIndex . '" t="inlineStr"><is><t>通过</t></is></c>';
                $newRows .= '</row>';
                
                $rowIndex++;
            }
        }
        
        // 在sheetData末尾插入新行
        $pattern = '/<\/sheetData>/';
        return preg_replace($pattern, $newRows . '</sheetData>', $xmlContent);
        
    } catch (Exception $e) {
        error_log("填充ChangeLog数据异常: " . $e->getMessage());
        return false;
    }
}

/**
 * 递归删除目录
 */
function deleteDirectory($dir) {
    if (!is_dir($dir)) {
        return unlink($dir);
    }
    
    $files = array_diff(scandir($dir), array('.', '..'));
    foreach ($files as $file) {
        $path = $dir . '/' . $file;
        is_dir($path) ? deleteDirectory($path) : unlink($path);
    }
    
    return rmdir($dir);
}

/**
 * 直接生成Excel文件（不使用模板）
 */
function generateExcelDirectly($outputPath, $deliveryRecord, $packageInfo, $pmsData) {
    try {
        // 创建一个简单的Excel XML格式文件
        $excelXml = '<?xml version="1.0" encoding="UTF-8"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
          xmlns:o="urn:schemas-microsoft-com:office:office"
          xmlns:x="urn:schemas-microsoft-com:office:excel"
          xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<Styles>
    <Style ss:ID="Header">
        <Font ss:Bold="1"/>
        <Interior ss:Color="#CCCCCC" ss:Pattern="Solid"/>
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
    </Style>
    <Style ss:ID="Bold">
        <Font ss:Bold="1"/>
    </Style>
</Styles>
<Worksheet ss:Name="提测信息">
    <Table>';

        // 第一行：主题名称+主题地址（合并在一个单元格，中间换行）
        $crpInfo = '主题名称：' . htmlspecialchars($deliveryRecord['crp_name'] ?? '') . '&#10;主题地址：' . htmlspecialchars($deliveryRecord['crp_addr'] ?? '');
        $excelXml .= '
        <Row>
            <Cell ss:MergeAcross="4"><Data ss:Type="String">' . $crpInfo . '</Data></Cell>
        </Row>';

        // 第二行：仓库地址
        $repoAddr = htmlspecialchars($deliveryRecord['repo_addr'] ?? ($deliveryRecord['project_repo'] ?? ''));
        $excelXml .= '
        <Row>
            <Cell ss:MergeAcross="4"><Data ss:Type="String">' . $repoAddr . '</Data></Cell>
        </Row>
        <Row><Cell></Cell></Row>';

        // 添加基本信息
        $excelXml .= '

        <Row><Cell></Cell></Row>';

        // 添加打包信息
        if (!empty($packageInfo)) {
            $excelXml .= '

        <Row>
            <Cell ss:StyleID="Header"><Data ss:Type="String">模块名*</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">包名*</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">应用版本*</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">哈希值*</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">类别(TASK或BUG)*</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">编号*</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">功能说明*</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">级别</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">更新翻译</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">影响范围(测试建议)</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">由谁解决/完成</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">自测人员</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">自测结果</Data></Cell>
            <Cell ss:StyleID="Header"><Data ss:Type="String">备注</Data></Cell>
        </Row>';

        // 先合并相同pms_url的PMS记录，将influence追加到一起
        $mergedPmsData = [];
        if (!empty($pmsData)) {
            foreach ($pmsData as $pms) {
                if (!empty($pms['pms_url'])) {
                    $url = $pms['pms_url'];
                    if (isset($mergedPmsData[$url])) {
                        // 如果已存在相同URL，追加influence
                        if (!empty($pms['influence'])) {
                            if (!empty($mergedPmsData[$url]['influence'])) {
                                $mergedPmsData[$url]['influence'] .= '; ' . $pms['influence'];
                            } else {
                                $mergedPmsData[$url]['influence'] = $pms['influence'];
                            }
                        }
                    } else {
                        // 新的URL，直接添加
                        $mergedPmsData[$url] = $pms;
                    }
                }
            }
        }

            foreach ($packageInfo as $package) {
                // 查找对应的PMS信息
                $pmsInfo = '';
                $pmsCategory = '';
                $pmsUrl = '';
                $pmsInfluence = '';
                $pmsAuthor = '';
                $cooperationTitle = ''; // 从协作平台获取的标题
                $cooperationLevel = ''; // 从协作平台获取的级别
                
                if (!empty($mergedPmsData)) {
                    $pmsData = reset($mergedPmsData); // 取第一个PMS数据
                    $pmsCategory = (stripos($pmsData['pms_url'], 'bug') !== false) ? 'BUG' : 'TASK';
                    $pmsUrl = $pmsData['pms_url'];
                    $pmsInfluence = $pmsData['influence'] ?? '';
                    $pmsAuthor = $pmsData['author'] ?? '';
                    $cooperationTitle = $pmsData['cooperation_title'] ?? ''; // 从协作平台获取的标题
                    $cooperationLevel = $pmsData['cooperation_level'] ?? ''; // 从协作平台获取的级别
                    array_shift($mergedPmsData); // 移除已使用的数据
                }
                
                $excelXml .= '
        <Row>
            <Cell><Data ss:Type="String">' . htmlspecialchars($package['module_name'] ?? '') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($package['module_name'] ?? '') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($package['cur_tag'] ?? '') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($package['build_commit'] ?? '') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($pmsCategory) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($pmsUrl) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($cooperationTitle) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($cooperationLevel) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars('否') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($pmsInfluence) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($pmsAuthor) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($pmsAuthor) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars('通过') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars('') . '</Data></Cell>
        </Row>';
            }
        }

        // PMS信息已经在上面的package循环中处理了
        // 如果还有剩余的PMS数据，单独添加行
        if (!empty($mergedPmsData)) {
            foreach ($mergedPmsData as $pms) {
                // 根据pms_url判断类别：包含bug返回BUG，否则返回TASK
                $category = (stripos($pms['pms_url'], 'bug') !== false) ? 'BUG' : 'TASK';
                $cooperationTitle = $pms['cooperation_title'] ?? '';
                $cooperationLevel = $pms['cooperation_level'] ?? '';
                
                $excelXml .= '
        <Row>
            <Cell></Cell>
            <Cell></Cell>
            <Cell></Cell>
            <Cell></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($category) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($pms['pms_url']) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($cooperationTitle) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($cooperationLevel) . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars('否') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($pms['influence'] ?? '') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($pms['author'] ?? '') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars($pms['author'] ?? '') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars('通过') . '</Data></Cell>
            <Cell><Data ss:Type="String">' . htmlspecialchars('') . '</Data></Cell>
        </Row>';
            }
        }

        $excelXml .= '
    </Table>
</Worksheet>
</Workbook>';

        // 写入文件
        $written = file_put_contents($outputPath, $excelXml);
        
        if ($written === false) {
            error_log("无法写入Excel文件: $outputPath");
            return false;
        }
        
        error_log("成功生成Excel文件: $outputPath (" . $written . " 字节)");
        return true;
        
    } catch (Exception $e) {
        error_log("生成Excel异常: " . $e->getMessage());
        return false;
    }
}

/**
 * 获取Gerrit项目的tag信息
 * @param string $moduleName 模块名称
 * @param string $tagName tag名称
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function getTagInfo($moduleName, $tagName, $db) {
    if (!$moduleName || !$tagName) {
        return [
            'success' => false,
            'message' => '模块名称和tag名称不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    // 构建Gerrit API URL
    $gerritUrl = "https://gerrit.uniontech.com/a/projects/" . urlencode($moduleName). "/tags/" . urlencode($tagName);
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    return [
        'success' => true,
        'message' => '成功获取tag信息',
        'data' => $result['data']
    ];
}

/**
 * 查询提交包含的分支和tag
 * @param string $moduleName 模块名称
 * @param string $commitId 提交ID
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function queryCommitIn($moduleName, $commitId, $db) {
    if (!$moduleName || !$commitId) {
        return [
            'success' => false,
            'message' => '模块名称和提交ID不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    // 构建Gerrit API URL
    $gerritUrl = "https://gerrit.uniontech.com/a/projects/" . urlencode($moduleName) . "/commits/" . urlencode($commitId)."/in";
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    // 解析返回的数据，提取branches和tags
    $data = $result['data'];
    $branches = null;
    $tags = null;
    
    if (isset($data['branches']) && is_array($data['branches']) && count($data['branches']) > 0) {
        $branches = $data['branches'];
    }
    
    if (isset($data['tags']) && is_array($data['tags']) && count($data['tags']) > 0) {
        $tags = $data['tags'];
    }
    
    return [
        'success' => true,
        'message' => '成功获取提交包含的分支和tag信息',
        'data' => [
            'branches' => $branches,
            'tags' => $tags
        ]
    ];
}

/**
 * 查询分支的最新提交是否打tag，并且查询落后多少
 * @param string $moduleName 模块名称
 * @param string $commitId 提交ID
 * @param Database $db 数据库实例
 * @return array 包含success、data、message的数组
 */
function queryBranchTag($moduleName, $commitId, $branchName, $db) {
    if (!$moduleName || !$commitId) {
        return [
            'success' => false,
            'message' => '模块名称和提交ID不能为空',
            'data' => null
        ];
    }
    
    $credentials = getGerritCredentials($db);
    if (!$credentials) {
        return [
            'success' => false,
            'message' => '无法获取Gerrit认证信息',
            'data' => null
        ];
    }
    
    // 构建Gerrit API URL
    $gerritUrl = "https://gerrit.uniontech.com/a/projects/" . urlencode($moduleName) . "/tags";
    $result = executeGerritRequest($gerritUrl, $credentials);
    
    if (!$result['success']) {
        return $result;
    }
    
    // 解析返回的数据，提取branches和tags
    $data = $result['data'];
    foreach ($data as $tag) {
        if (isset($tag['object']) && $tag['object'] == $commitId) {
            return [
                'success' => true,
                'message' => '成功获取提交包含的分支和tag信息',
                'data' => [
                    'tagInfo' => $tag['message'],
                    'tag' => str_replace("refs/tags/", "", $tag['ref'])
                ]
            ];
        }
    }

    return [
        'success' => false,
        'message' => '没有获取到',
        'data' => [
            'tagInfo' => null,
            'tag' => null
        ]
    ];
}

?>
