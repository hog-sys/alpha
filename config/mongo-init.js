// config/mongo-init.js
// MongoDB 初始化脚本 - 为 Infisical 创建数据库和用户

// 切换到 infisical 数据库
db = db.getSiblingDB('infisical');

// 创建 infisical 应用用户
db.createUser({
  user: 'infisical_app',
  pwd: 'InfisicalApp123!',
  roles: [
    {
      role: 'readWrite',
      db: 'infisical'
    }
  ]
});

// 创建初始集合和索引
db.createCollection('users');
db.createCollection('projects');
db.createCollection('secrets');
db.createCollection('audit_logs');

// 为用户集合创建索引
db.users.createIndex({ "email": 1 }, { unique: true });
db.users.createIndex({ "createdAt": 1 });

// 为项目集合创建索引
db.projects.createIndex({ "name": 1 });
db.projects.createIndex({ "ownerId": 1 });
db.projects.createIndex({ "createdAt": 1 });

// 为密钥集合创建索引
db.secrets.createIndex({ "projectId": 1, "environment": 1, "key": 1 }, { unique: true });
db.secrets.createIndex({ "projectId": 1 });
db.secrets.createIndex({ "updatedAt": 1 });

// 为审计日志创建索引
db.audit_logs.createIndex({ "projectId": 1 });
db.audit_logs.createIndex({ "userId": 1 });
db.audit_logs.createIndex({ "timestamp": 1 });
db.audit_logs.createIndex({ "timestamp": 1 }, { expireAfterSeconds: 7776000 }); // 90天过期

// 插入默认管理员用户（如果需要）
// 注意：实际生产环境中应该通过API创建用户
print('MongoDB 初始化完成 - Infisical 数据库已准备就绪');
