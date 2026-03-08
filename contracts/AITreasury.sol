// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";

interface IFreedomToken {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function mint(address to, uint256 amount) external;
    function burnFrom(address from, uint256 amount) external;
}

/**
 * @title AITreasury
 * @author FreedomToken Team
 * @notice Treasury management with AI-assisted allocation and multi-sig security
 * @dev Handles protocol funds, staking rewards, and community grants
 *      with automated yield strategies and emergency controls
 * @custom:security-contact security@freedomtoken.io
 */
contract AITreasury is AccessControl, ReentrancyGuard {
    using SafeERC20 for IERC20;
    using Address for address;

    // ============ Roles ============
    bytes32 public constant AI_CONTROLLER_ROLE = keccak256("AI_CONTROLLER_ROLE");
    bytes32 public constant ALLOCATION_MANAGER_ROLE = keccak256("ALLOCATION_MANAGER_ROLE");
    bytes32 public constant EMERGENCY_GUARDIAN_ROLE = keccak256("EMERGENCY_GUARDIAN_ROLE");
    bytes32 public constant YIELD_MANAGER_ROLE = keccak256("YIELD_MANAGER_ROLE");

    // ============ Token References ============
    IFreedomToken public immutable freedomToken;
    
    // ============ Fund Allocation Categories ============
    enum AllocationCategory {
        StakingRewards,
        CommunityGrants,
        Development,
        Marketing,
        Liquidity,
        EmergencyReserve,
        AIInvestment
    }

    struct Allocation {
        AllocationCategory category;
        uint256 percentage; // Basis points (10000 = 100%)
        uint256 allocated;
        uint256 spent;
        address recipient;
        bool active;
    }

    // ============ Allocation Storage ============
    mapping(AllocationCategory => Allocation) public allocations;
    mapping(uint256 => AllocationCategory) public categoryByIndex;
    uint256 public constant ALLOCATION_COUNT = 7;
    
    // Basis points constants
    uint256 public constant BASIS_POINTS = 10000;
    uint256 public constant MAX_ALLOCATION_PERCENT = 5000; // 50% max per category

    // ============ Spending Limits ============
    struct SpendingLimit {
        uint256 dailyLimit;
        uint256 monthlyLimit;
        uint256 spentToday;
        uint256 spentThisMonth;
        uint256 lastResetDay;
        uint256 lastResetMonth;
    }
    
    mapping(AllocationCategory => SpendingLimit) public spendingLimits;
    mapping(bytes32 => bool) public processedTransactions;

    // ============ AI Investment Strategies ============
    struct AIInvestment {
        uint256 id;
        string strategy;
        address targetAsset;
        uint256 amount;
        uint256 expectedReturn; // Basis points
        uint256 riskScore; // 1-100
        uint256 timestamp;
        bool executed;
        bool profitable;
        uint256 actualReturn;
    }
    
    mapping(uint256 => AIInvestment) public aiInvestments;
    uint256 public aiInvestmentCount;
    uint256 public constant MAX_AI_INVESTMENT_PERCENT = 1000; // 10% of treasury
    uint256 public constant MIN_RISK_SCORE = 30; // Minimum risk tolerance
    uint256 public constant MAX_RISK_SCORE = 70; // Maximum risk allowed

    // ============ Multi-Sig Configuration ============
    struct MultiSigRequest {
        bytes32 txHash;
        address[] signers;
        mapping(address => bool) hasSigned;
        uint256 requiredSigs;
        uint256 currentSigs;
        uint256 timestamp;
        bool executed;
        AllocationCategory category;
        uint256 amount;
        address recipient;
        bytes data;
    }
    
    mapping(bytes32 => MultiSigRequest) public multiSigRequests;
    uint256 public constant MULTI_SIG_THRESHOLD = 3; // 3 signatures required
    uint256 public constant MULTI_SIG_TIMELOCK = 2 days;

    // ============ Yield Strategy ============
    struct YieldStrategy {
        address protocol;
        uint256 allocatedAmount;
        uint256 currentValue;
        uint256 apy; // Basis points
        uint256 lastHarvest;
        bool active;
    }
    
    mapping(address => YieldStrategy) public yieldStrategies;
    address[] public activeYieldProtocols;
    uint256 public totalYieldAllocated;
    uint256 public constant MAX_YIELD_ALLOCATION = 3000; // 30% of treasury max

    // ============ Emergency Controls ============
    bool public emergencyPaused;
    uint256 public emergencyFundReserved;
    uint256 public constant EMERGENCY_RESERVE_PERCENT = 2000; // 20%
    mapping(address => bool) public blacklisted;

    // ============ Events ============
    event FundsAllocated(
        AllocationCategory indexed category,
        uint256 amount,
        address indexed recipient
    );
    event FundsSpent(
        AllocationCategory indexed category,
        uint256 amount,
        address indexed recipient,
        string reason
    );
    event AIInvestmentProposed(
        uint256 indexed investmentId,
        string strategy,
        uint256 amount,
        uint256 riskScore
    );
    event AIInvestmentExecuted(
        uint256 indexed investmentId,
        bool success,
        uint256 actualReturn
    );
    event YieldHarvested(
        address indexed protocol,
        uint256 amount,
        uint256 newApy
    );
    event MultiSigRequestCreated(
        bytes32 indexed txHash,
        AllocationCategory category,
        uint256 amount
    );
    event MultiSigSigned(
        bytes32 indexed txHash,
        address indexed signer,
        uint256 currentCount
    );
    event MultiSigExecuted(bytes32 indexed txHash);
    event EmergencyPauseToggled(bool paused);
    event EmergencyWithdrawal(address indexed token, uint256 amount, address to);
    event AllocationUpdated(
        AllocationCategory category,
        uint256 newPercentage,
        address newRecipient
    );
    event BlacklistUpdated(address indexed account, bool blacklisted);

    // ============ Errors ============
    error InvalidCategory(AllocationCategory category);
    error InvalidPercentage(uint256 percentage, uint256 max);
    error AllocationMismatch(uint256 total, uint256 expected);
    error InsufficientFunds(AllocationCategory category, uint256 requested, uint256 available);
    error SpendingLimitExceeded(AllocationCategory category, uint256 requested, uint256 limit);
    error MultiSigAlreadySigned(bytes32 txHash, address signer);
    error MultiSigNotFound(bytes32 txHash);
    error MultiSigInsufficientSignatures(bytes32 txHash, uint256 current, uint256 required);
    error MultiSigTimelockActive(bytes32 txHash, uint256 unlockTime);
    error MultiSigExpired(bytes32 txHash);
    error AIInvestmentRiskTooHigh(uint256 riskScore, uint256 maxAllowed);
    error AIInvestmentAmountTooHigh(uint256 amount, uint256 maxAllowed);
    error YieldStrategyNotFound(address protocol);
    error YieldAllocationExceeded(uint256 requested, uint256 max);
    error EmergencyPaused();
    error AddressBlacklisted(address account);
    error TransactionAlreadyProcessed(bytes32 txHash);
    error InvalidRecipient(address recipient);
    error ZeroAmount();
    error EmergencyReserveInsufficient(uint256 requested, uint256 available);

    // ============ Modifiers ============
    modifier notPaused() {
        if (emergencyPaused) revert EmergencyPaused();
        _;
    }

    modifier notBlacklisted(address account) {
        if (blacklisted[account]) revert AddressBlacklisted(account);
        _;
    }

    // ============ Constructor ============
    /**
     * @notice Initializes AITreasury
     * @param _freedomToken Address of FreedomToken contract
     * @param _admin Address with admin role
     * @param _aiController AI controller address
     * @param _guardian Emergency guardian address
     */
    constructor(
        address _freedomToken,
        address _admin,
        address _aiController,
        address _guardian
    ) {
        if (_freedomToken == address(0)) revert InvalidRecipient(_freedomToken);
        if (_admin == address(0)) revert InvalidRecipient(_admin);
        
        freedomToken = IFreedomToken(_freedomToken);
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(AI_CONTROLLER_ROLE, _aiController);
        _grantRole(EMERGENCY_GUARDIAN_ROLE, _guardian);
        _grantRole(ALLOCATION_MANAGER_ROLE, _admin);
        _grantRole(YIELD_MANAGER_ROLE, _admin);

        // Initialize allocation categories
        categoryByIndex[0] = AllocationCategory.StakingRewards;
        categoryByIndex[1] = AllocationCategory.CommunityGrants;
        categoryByIndex[2] = AllocationCategory.Development;
        categoryByIndex[3] = AllocationCategory.Marketing;
        categoryByIndex[4] = AllocationCategory.Liquidity;
        categoryByIndex[5] = AllocationCategory.EmergencyReserve;
        categoryByIndex[6] = AllocationCategory.AIInvestment;

        // Set default allocations (percentages)
        allocations[AllocationCategory.StakingRewards] = Allocation({
            category: AllocationCategory.StakingRewards,
            percentage: 3000, // 30%
            allocated: 0,
            spent: 0,
            recipient: _admin,
            active: true
        });

        allocations[AllocationCategory.CommunityGrants] = Allocation({
            category: AllocationCategory.CommunityGrants,
            percentage: 1500, // 15%
            allocated: 0,
            spent: 0,
            recipient: _admin,
            active: true
        });

        allocations[AllocationCategory.Development] = Allocation({
            category: AllocationCategory.Development,
            percentage: 1500, // 15%
            allocated: 0,
            spent: 0,
            recipient: _admin,
            active: true
        });

        allocations[AllocationCategory.Marketing] = Allocation({
            category: AllocationCategory.Marketing,
            percentage: 1000, // 10%
            allocated: 0,
            spent: 0,
            recipient: _admin,
            active: true
        });

        allocations[AllocationCategory.Liquidity] = Allocation({
            category: AllocationCategory.Liquidity,
            percentage: 1000, // 10%
            allocated: 0,
            spent: 0,
            recipient: _admin,
            active: true
        });

        allocations[AllocationCategory.EmergencyReserve] = Allocation({
            category: AllocationCategory.EmergencyReserve,
            percentage: 1500, // 15%
            allocated: 0,
            spent: 0,
            recipient: _admin,
            active: true
        });

        allocations[AllocationCategory.AIInvestment] = Allocation({
            category: AllocationCategory.AIInvestment,
            percentage: 500, // 5%
            allocated: 0,
            spent: 0,
            recipient: _admin,
            active: true
        });
    }

    // ============ Fund Management ============
    /**
     * @notice Deposit funds into treasury
     * @param amount Amount to deposit
     */
    function deposit(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();
        
        IERC20(address(freedomToken)).safeTransferFrom(msg.sender, address(this), amount);
        
        // Allocate according to percentages
        _allocateIncomingFunds(amount);
    }

    /**
     * @notice Internal fund allocation
     * @param amount Amount to allocate
     */
    function _allocateIncomingFunds(uint256 amount) internal {
        for (uint256 i = 0; i < ALLOCATION_COUNT; i++) {
            AllocationCategory cat = categoryByIndex[i];
            Allocation storage alloc = allocations[cat];
            
            if (alloc.active) {
                uint256 allocationAmount = (amount * alloc.percentage) / BASIS_POINTS;
                alloc.allocated += allocationAmount;
                
                // Track emergency reserve separately
                if (cat == AllocationCategory.EmergencyReserve) {
                    emergencyFundReserved += allocationAmount;
                }
            }
        }
    }

    // ============ Spending ============
    /**
     * @notice Spend funds from allocation (requires multi-sig for large amounts)
     * @param category Allocation category
     * @param amount Amount to spend
     * @param recipient Recipient address
     * @param reason Reason for spending
     */
    function spend(
        AllocationCategory category,
        uint256 amount,
        address recipient,
        string calldata reason
    ) external onlyRole(ALLOCATION_MANAGER_ROLE) notPaused notBlacklisted(recipient) nonReentrant {
        if (amount == 0) revert ZeroAmount();
        if (recipient == address(0)) revert InvalidRecipient(recipient);
        
        Allocation storage alloc = allocations[category];
        if (!alloc.active) revert InvalidCategory(category);
        
        // Check category balance
        uint256 available = alloc.allocated - alloc.spent;
        if (amount > available) {
            revert InsufficientFunds(category, amount, available);
        }
        
        // Check spending limits
        _checkSpendingLimit(category, amount);
        
        // Multi-sig required for large amounts (> 1% of treasury)
        uint256 treasuryBalance = IERC20(address(freedomToken)).balanceOf(address(this));
        if (amount > treasuryBalance / 100) {
            revert MultiSigNotFound(keccak256(abi.encodePacked(category, amount, recipient, block.timestamp)));
        }
        
        // Update spending tracking
        alloc.spent += amount;
        _updateSpendingTracking(category, amount);
        
        // Transfer funds
        IERC20(address(freedomToken)).safeTransfer(recipient, amount);
        
        emit FundsSpent(category, amount, recipient, reason);
    }

    /**
     * @notice Check and update spending limits
     */
    function _checkSpendingLimit(AllocationCategory category, uint256 amount) internal view {
        SpendingLimit storage limit = spendingLimits[category];
        
        // Check daily limit
        if (limit.dailyLimit > 0) {
            uint256 day = block.timestamp / 1 days;
            uint256 spentToday = limit.lastResetDay == day ? limit.spentToday : 0;
            if (spentToday + amount > limit.dailyLimit) {
                revert SpendingLimitExceeded(category, amount, limit.dailyLimit - spentToday);
            }
        }
        
        // Check monthly limit
        if (limit.monthlyLimit > 0) {
            uint256 month = block.timestamp / 30 days;
            uint256 spentThisMonth = limit.lastResetMonth == month ? limit.spentThisMonth : 0;
            if (spentThisMonth + amount > limit.monthlyLimit) {
                revert SpendingLimitExceeded(category, amount, limit.monthlyLimit - spentThisMonth);
            }
        }
    }

    function _updateSpendingTracking(AllocationCategory category, uint256 amount) internal {
        SpendingLimit storage limit = spendingLimits[category];
        
        uint256 day = block.timestamp / 1 days;
        if (limit.lastResetDay != day) {
            limit.spentToday = 0;
            limit.lastResetDay = day;
        }
        limit.spentToday += amount;
        
        uint256 month = block.timestamp / 30 days;
        if (limit.lastResetMonth != month) {
            limit.spentThisMonth = 0;
            limit.lastResetMonth = month;
        }
        limit.spentThisMonth += amount;
    }

    // ============ AI Investment ============
    /**
     * @notice Propose AI investment strategy
     * @param strategy Description of strategy
     * @param targetAsset Asset to invest in
     * @param amount Investment amount
     * @param expectedReturn Expected return (basis points)
     * @param riskScore Risk score 1-100
     * @return investmentId ID of proposed investment
     */
    function proposeAIInvestment(
        string calldata strategy,
        address targetAsset,
        uint256 amount,
        uint256 expectedReturn,
        uint256 riskScore
    ) external onlyRole(AI_CONTROLLER_ROLE) notPaused returns (uint256) {
        if (targetAsset == address(0)) revert InvalidRecipient(targetAsset);
        if (amount == 0) revert ZeroAmount();
        if (riskScore < MIN_RISK_SCORE || riskScore > MAX_RISK_SCORE) {
            revert AIInvestmentRiskTooHigh(riskScore, MAX_RISK_SCORE);
        }
        
        // Check max AI investment allocation
        Allocation storage aiAlloc = allocations[AllocationCategory.AIInvestment];
        uint256 maxInvestment = (aiAlloc.allocated * MAX_AI_INVESTMENT_PERCENT) / BASIS_POINTS;
        if (amount > maxInvestment) {
            revert AIInvestmentAmountTooHigh(amount, maxInvestment);
        }
        
        uint256 investmentId = aiInvestmentCount++;
        aiInvestments[investmentId] = AIInvestment({
            id: investmentId,
            strategy: strategy,
            targetAsset: targetAsset,
            amount: amount,
            expectedReturn: expectedReturn,
            riskScore: riskScore,
            timestamp: block.timestamp,
            executed: false,
            profitable: false,
            actualReturn: 0
        });
        
        emit AIInvestmentProposed(investmentId, strategy, amount, riskScore);
        return investmentId;
    }

    /**
     * @notice Execute approved AI investment (requires multi-sig)
     * @param investmentId Investment to execute
     */
    function executeAIInvestment(uint256 investmentId) external onlyRole(ALLOCATION_MANAGER_ROLE) nonReentrant {
        AIInvestment storage investment = aiInvestments[investmentId];
        if (investment.executed) revert TransactionAlreadyProcessed(bytes32(investmentId));
        
        investment.executed = true;
        
        Allocation storage aiAlloc = allocations[AllocationCategory.AIInvestment];
        aiAlloc.spent += investment.amount;
        
        // Transfer to investment target
        IERC20(address(freedomToken)).safeTransfer(investment.targetAsset, investment.amount);
        
        emit AIInvestmentExecuted(investmentId, true, 0);
    }

    /**
     * @notice Report AI investment results
     * @param investmentId Investment to report on
     * @param profitable Whether it was profitable
     * @param actualReturn Actual return (basis points)
     */
    function reportAIInvestmentResults(
        uint256 investmentId,
        bool profitable,
        uint256 actualReturn
    ) external onlyRole(AI_CONTROLLER_ROLE) {
        AIInvestment storage investment = aiInvestments[investmentId];
        if (!investment.executed) revert InvalidCategory(AllocationCategory.AIInvestment);
        
        investment.profitable = profitable;
        investment.actualReturn = actualReturn;
        
        emit AIInvestmentExecuted(investmentId, profitable, actualReturn);
    }

    // ============ Multi-Sig Functions ============
    /**
     * @notice Create multi-sig request for large spending
     * @param category Allocation category
     * @param amount Amount to spend
     * @param recipient Recipient address
     * @param data Additional data
     * @return txHash Hash of transaction
     */
    function createMultiSigRequest(
        AllocationCategory category,
        uint256 amount,
        address recipient,
        bytes calldata data
    ) external onlyRole(ALLOCATION_MANAGER_ROLE) returns (bytes32) {
        bytes32 txHash = keccak256(abi.encodePacked(
            category,
            amount,
            recipient,
            data,
            block.timestamp
        ));
        
        if (multiSigRequests[txHash].timestamp != 0) {
            revert TransactionAlreadyProcessed(txHash);
        }
        
        MultiSigRequest storage request = multiSigRequests[txHash];
        request.txHash = txHash;
        request.requiredSigs = MULTI_SIG_THRESHOLD;
        request.timestamp = block.timestamp;
        request.executed = false;
        request.category = category;
        request.amount = amount;
        request.recipient = recipient;
        request.data = data;
        
        emit MultiSigRequestCreated(txHash, category, amount);
        return txHash;
    }

    /**
     * @notice Sign multi-sig request
     * @param txHash Transaction to sign
     */
    function signMultiSigRequest(bytes32 txHash) external onlyRole(ALLOCATION_MANAGER_ROLE) {
        MultiSigRequest storage request = multiSigRequests[txHash];
        if (request.timestamp == 0) revert MultiSigNotFound(txHash);
        if (request.executed) revert TransactionAlreadyProcessed(txHash);
        if (request.hasSigned[msg.sender]) revert MultiSigAlreadySigned(txHash, msg.sender);
        
        request.hasSigned[msg.sender] = true;
        request.currentSigs++;
        
        emit MultiSigSigned(txHash, msg.sender, request.currentSigs);
    }

    /**
     * @notice Execute multi-sig request after threshold met
     * @param txHash Transaction to execute
     */
    function executeMultiSigRequest(bytes32 txHash) external onlyRole(ALLOCATION_MANAGER_ROLE) nonReentrant {
        MultiSigRequest storage request = multiSigRequests[txHash];
        if (request.timestamp == 0) revert MultiSigNotFound(txHash);
        if (request.executed) revert TransactionAlreadyProcessed(txHash);
        if (request.currentSigs < request.requiredSigs) {
            revert MultiSigInsufficientSignatures(txHash, request.currentSigs, request.requiredSigs);
        }
        if (block.timestamp < request.timestamp + MULTI_SIG_TIMELOCK) {
            revert MultiSigTimelockActive(txHash, request.timestamp + MULTI_SIG_TIMELOCK);
        }
        if (block.timestamp > request.timestamp + MULTI_SIG_TIMELOCK + 7 days) {
            revert MultiSigExpired(txHash);
        }
        
        request.executed = true;
        
        // Execute spending
        Allocation storage alloc = allocations[request.category];
        alloc.spent += request.amount;
        
        IERC20(address(freedomToken)).safeTransfer(request.recipient, request.amount);
        
        emit MultiSigExecuted(txHash);
    }

    // ============ Emergency Functions ============
    /**
     * @notice Emergency pause
     */
    function emergencyPause() external onlyRole(EMERGENCY_GUARDIAN_ROLE) {
        emergencyPaused = true;
        emit EmergencyPauseToggled(true);
    }

    /**
     * @notice Emergency unpause
     */
    function emergencyUnpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        emergencyPaused = false;
        emit EmergencyPauseToggled(false);
    }

    /**
     * @notice Emergency withdrawal of all funds
     * @param to Address to withdraw to
     */
    function emergencyWithdrawal(address to) external onlyRole(EMERGENCY_GUARDIAN_ROLE) nonReentrant {
        if (to == address(0)) revert InvalidRecipient(to);
        
        uint256 balance = IERC20(address(freedomToken)).balanceOf(address(this));
        IERC20(address(freedomToken)).safeTransfer(to, balance);
        
        emit EmergencyWithdrawal(address(freedomToken), balance, to);
    }

    /**
     * @notice Update blacklist status
     * @param account Address to update
     * @param isBlacklisted New status
     */
    function setBlacklist(address account, bool isBlacklisted) external onlyRole(DEFAULT_ADMIN_ROLE) {
        blacklisted[account] = isBlacklisted;
        emit BlacklistUpdated(account, isBlacklisted);
    }

    // ============ View Functions ============
    /**
     * @notice Get treasury balance
     */
    function getTreasuryBalance() external view returns (uint256) {
        return IERC20(address(freedomToken)).balanceOf(address(this));
    }

    /**
     * @notice Get allocation details
     * @param category Category to query
     */
    function getAllocationDetails(AllocationCategory category) external view returns (
        uint256 percentage,
        uint256 allocated,
        uint256 spent,
        uint256 available,
        address recipient,
        bool active
    ) {
        Allocation storage alloc = allocations[category];
        return (
            alloc.percentage,
            alloc.allocated,
            alloc.spent,
            alloc.allocated - alloc.spent,
            alloc.recipient,
            alloc.active
        );
    }

    /**
     * @notice Check if transaction needs multi-sig
     * @param amount Amount to check
     */
    function requiresMultiSig(uint256 amount) external view returns (bool) {
        uint256 treasuryBalance = IERC20(address(freedomToken)).balanceOf(address(this));
        return amount > treasuryBalance / 100; // > 1% requires multi-sig
    }
}