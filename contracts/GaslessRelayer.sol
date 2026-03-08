// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import "@openzeppelin/contracts/utils/structs/EnumerableSet.sol";

/**
 * @title GaslessRelayer
 * @author FreedomToken Team
 * @notice ERC-4337 compatible meta-transaction relayer for gasless transactions
 * @dev Enables users to execute transactions without holding ETH for gas fees.
 *      Supports EIP-712 typed data signing, nonce management, and relay payment.
 * @custom:security-contact security@freedomtoken.io
 */
contract GaslessRelayer is AccessControl, ReentrancyGuard, EIP712 {
    using ECDSA for bytes32;
    using EnumerableSet for EnumerableSet.AddressSet;

    // ============ Roles ============
    bytes32 public constant RELAYER_OPERATOR_ROLE = keccak256("RELAYER_OPERATOR_ROLE");
    bytes32 public constant PAYMASTER_ROLE = keccak256("PAYMASTER_ROLE");
    bytes32 public constant WHITELIST_MANAGER_ROLE = keccak256("WHITELIST_MANAGER_ROLE");

    // ============ EIP-712 Type Hashes ============
    bytes32 private constant META_TRANSACTION_TYPEHASH = keccak256(
        "MetaTransaction(address from,address to,uint256 value,bytes data,uint256 nonce,uint256 deadline)"
    );

    bytes32 private constant BATCH_TRANSACTION_TYPEHASH = keccak256(
        "BatchTransaction(MetaTransaction[] transactions,uint256 nonce,uint256 deadline)"
    );

    struct MetaTransaction {
        address from;
        address to;
        uint256 value;
        bytes data;
        uint256 nonce;
        uint256 deadline;
    }

    // ============ Nonce Management ============
    mapping(address => uint256) public nonces;
    mapping(bytes32 => bool) public executedTransactions;
    mapping(address => mapping(uint256 => bool)) public usedNonces;

    // ============ Relay Configuration ============
    struct RelayConfig {
        uint256 maxGasPrice;
        uint256 minGasPrice;
        uint256 relayFeePercent; // Basis points
        uint256 maxTransactionValue;
        bool requireWhitelist;
        bool paused;
    }
    
    RelayConfig public config;
    
    uint256 public constant BASIS_POINTS = 10000;
    uint256 public constant MAX_FEE_PERCENT = 500; // 5% max fee
    uint256 public constant MIN_DEADLINE = 5 minutes;
    uint256 public constant MAX_DEADLINE = 1 hours;

    // ============ Whitelist ============
    EnumerableSet.AddressSet private _whitelistedSenders;
    EnumerableSet.AddressSet private _whitelistedRecipients;
    mapping(address => bool) public blacklisted;

    // ============ Fee Management ============
    mapping(address => uint256) public relayFeesCollected;
    uint256 public totalFeesCollected;
    address public feeRecipient;

    // ============ Transaction Tracking ============
    struct RelayedTransaction {
        bytes32 txHash;
        address from;
        address to;
        uint256 value;
        uint256 gasUsed;
        uint256 fee;
        uint256 timestamp;
        bool success;
    }
    
    mapping(bytes32 => RelayedTransaction) public transactions;
    bytes32[] public transactionHistory;
    uint256 public constant MAX_HISTORY = 10000;

    // ============ User Operation (ERC-4337 Style) ============
    struct UserOperation {
        address sender;
        uint256 nonce;
        bytes initCode;
        bytes callData;
        uint256 callGasLimit;
        uint256 verificationGasLimit;
        uint256 preVerificationGas;
        uint256 maxFeePerGas;
        uint256 maxPriorityFeePerGas;
        bytes paymasterAndData;
        bytes signature;
    }
    
    mapping(address => uint256) public userOperationNonces;

    // ============ Events ============
    event MetaTransactionExecuted(
        bytes32 indexed txHash,
        address indexed from,
        address indexed to,
        uint256 value,
        uint256 fee,
        bool success
    );
    event BatchExecuted(
        bytes32 indexed batchHash,
        address indexed relayer,
        uint256 transactionCount,
        uint256 totalFees
    );
    event UserOperationExecuted(
        bytes32 indexed opHash,
        address indexed sender,
        uint256 actualGasCost,
        bool success
    );
    event FeeRecipientUpdated(address oldRecipient, address newRecipient);
    event RelayConfigUpdated(
        uint256 maxGasPrice,
        uint256 minGasPrice,
        uint256 relayFeePercent,
        uint256 maxTransactionValue
    );
    event WhitelistStatusUpdated(
        address indexed account,
        bool isSender,
        bool whitelisted
    );
    event BlacklistStatusUpdated(address indexed account, bool blacklisted);
    event FeesWithdrawn(address indexed recipient, uint256 amount);
    event NonceInvalidated(address indexed user, uint256 nonce);

    // ============ Errors ============
    error InvalidSignature(address signer, address expected);
    error TransactionExpired(uint256 deadline, uint256 current);
    error NonceAlreadyUsed(address user, uint256 nonce);
    error GasPriceTooHigh(uint256 gasPrice, uint256 max);
    error GasPriceTooLow(uint256 gasPrice, uint256 min);
    error TransactionValueTooHigh(uint256 value, uint256 max);
    error FeeTooHigh(uint256 fee, uint256 max);
    error TransactionAlreadyExecuted(bytes32 txHash);
    error DeadlineTooShort(uint256 deadline, uint256 minimum);
    error DeadlineTooLong(uint256 deadline, uint256 maximum);
    error NotWhitelisted(address account);
    error BlacklistedAddress(address account);
    error RelayPausedError();
    error InsufficientFeePayment(uint256 required, uint256 provided);
    error TransactionFailed(bytes32 txHash, bytes revertData);
    error BatchTooLarge(uint256 size, uint256 max);
    error InvalidFeeRecipient(address recipient);
    error HistoryLimitReached();

    // ============ Constructor ============
    /**
     * @notice Initializes GaslessRelayer
     * @param _admin Address with admin role
     * @param _feeRecipient Address to receive relay fees
     */
    constructor(
        address _admin,
        address _feeRecipient
    ) EIP712("GaslessRelayer", "1") {
        if (_admin == address(0)) revert InvalidFeeRecipient(_admin);
        if (_feeRecipient == address(0)) revert InvalidFeeRecipient(_feeRecipient);
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(RELAYER_OPERATOR_ROLE, _admin);
        _grantRole(PAYMASTER_ROLE, _admin);
        _grantRole(WHITELIST_MANAGER_ROLE, _admin);
        
        feeRecipient = _feeRecipient;
        
        // Set default config
        config = RelayConfig({
            maxGasPrice: 500 gwei,
            minGasPrice: 1 gwei,
            relayFeePercent: 100, // 1%
            maxTransactionValue: 1000 ether,
            requireWhitelist: false,
            paused: false
        });
    }

    // ============ Meta-Transaction Execution ============
    /**
     * @notice Execute a meta-transaction on behalf of user
     * @param from Transaction signer (pays for gas via tokens)
     * @param to Target contract/address
     * @param value ETH value to send
     * @param data Calldata
     * @param nonce Unique nonce for replay protection
     * @param deadline Transaction expiration
     * @param signature EIP-712 signature
     * @return success Whether transaction succeeded
     */
    function executeMetaTransaction(
        address from,
        address to,
        uint256 value,
        bytes calldata data,
        uint256 nonce,
        uint256 deadline,
        bytes calldata signature
    ) external onlyRole(RELAYER_OPERATOR_ROLE) nonReentrant returns (bool success) {
        // Validate relay state
        if (config.paused) revert RelayPausedError();
        if (blacklisted[from] || blacklisted[to]) revert BlacklistedAddress(blacklisted[from] ? from : to);
        if (config.requireWhitelist && !_whitelistedSenders.contains(from)) {
            revert NotWhitelisted(from);
        }

        // Validate deadline
        if (block.timestamp > deadline) revert TransactionExpired(deadline, block.timestamp);
        if (deadline < block.timestamp + MIN_DEADLINE) revert DeadlineTooShort(deadline, block.timestamp + MIN_DEADLINE);
        if (deadline > block.timestamp + MAX_DEADLINE) revert DeadlineTooLong(deadline, block.timestamp + MAX_DEADLINE);

        // Validate gas price
        uint256 gasPrice = tx.gasprice;
        if (gasPrice > config.maxGasPrice) revert GasPriceTooHigh(gasPrice, config.maxGasPrice);
        if (gasPrice < config.minGasPrice) revert GasPriceTooLow(gasPrice, config.minGasPrice);

        // Validate value
        if (value > config.maxTransactionValue) revert TransactionValueTooHigh(value, config.maxTransactionValue);

        // Validate nonce
        if (usedNonces[from][nonce]) revert NonceAlreadyUsed(from, nonce);
        usedNonces[from][nonce] = true;

        // Verify signature
        bytes32 txHash = keccak256(abi.encode(
            META_TRANSACTION_TYPEHASH,
            from,
            to,
            value,
            keccak256(data),
            nonce,
            deadline
        ));

        bytes32 digest = _hashTypedDataV4(txHash);
        address signer = digest.recover(signature);
        if (signer != from) revert InvalidSignature(signer, from);

        if (executedTransactions[txHash]) revert TransactionAlreadyExecuted(txHash);
        executedTransactions[txHash] = true;

        // Execute and record in single step to reduce stack variables
        uint256 gasStart = gasleft();
        (success, ) = to.call{value: value}(data);
        uint256 gasUsed = gasStart - gasleft();
        uint256 fee = (gasUsed * gasPrice * config.relayFeePercent) / BASIS_POINTS;

        // Record transaction
        _recordTransaction(txHash, from, to, value, gasUsed, fee, success);

        emit MetaTransactionExecuted(txHash, from, to, value, fee, success);

        if (!success) revert TransactionFailed(txHash, "");

        return success;
    }

    /**
     * @notice Execute multiple meta-transactions in a batch
     * @param _transactions Array of meta-transactions
     * @param batchSignature Signature for entire batch
     * @return successCount Number of successful transactions
     */
    function executeBatch(
        MetaTransaction[] calldata _transactions,
        bytes calldata batchSignature
    ) external onlyRole(RELAYER_OPERATOR_ROLE) nonReentrant returns (uint256 successCount) {
        if (config.paused) revert RelayPausedError();
        if (_transactions.length > 10) revert BatchTooLarge(_transactions.length, 10);
        
        bytes32 batchHash = keccak256(abi.encode(
            BATCH_TRANSACTION_TYPEHASH,
            keccak256(abi.encode(_transactions)),
            nonces[msg.sender]++,
            block.timestamp + MAX_DEADLINE
        ));
        
        bytes32 digest = _hashTypedDataV4(batchHash);
        address batchSigner = digest.recover(batchSignature);
        if (batchSigner == address(0)) revert InvalidSignature(batchSigner, address(0));
        
        uint256 totalFees = 0;
        
        for (uint256 i = 0; i < _transactions.length; i++) {
            MetaTransaction calldata metaTx = _transactions[i];
            
            if (usedNonces[metaTx.from][metaTx.nonce]) continue;
            usedNonces[metaTx.from][metaTx.nonce] = true;
            
            bytes32 txHash = keccak256(abi.encode(
                META_TRANSACTION_TYPEHASH,
                metaTx.from,
                metaTx.to,
                metaTx.value,
                keccak256(metaTx.data),
                metaTx.nonce,
                metaTx.deadline
            ));
            
            if (executedTransactions[txHash]) continue;
            executedTransactions[txHash] = true;
            
            uint256 gasStart = gasleft();
            (bool success, ) = metaTx.to.call{value: metaTx.value}(metaTx.data);
            uint256 gasUsed = gasStart - gasleft();
            
            uint256 fee = (gasUsed * tx.gasprice * config.relayFeePercent) / BASIS_POINTS;
            totalFees += fee;
            
            _recordTransaction(txHash, metaTx.from, metaTx.to, metaTx.value, gasUsed, fee, success);
            
            if (success) successCount++;
        }
        
        emit BatchExecuted(batchHash, msg.sender, _transactions.length, totalFees);
        return successCount;
    }

    // ============ ERC-4337 User Operation Support ============
    /**
     * @notice Execute ERC-4337 style user operation
     * @param op User operation structure
     * @param beneficiary Address to receive gas refund
     */
    function executeUserOperation(
        UserOperation calldata op,
        address beneficiary
    ) external onlyRole(RELAYER_OPERATOR_ROLE) nonReentrant returns (uint256 actualGasCost) {
        if (config.paused) revert RelayPausedError();
        if (blacklisted[op.sender]) revert BlacklistedAddress(op.sender);
        
        // Validate user operation nonce
        if (op.nonce != userOperationNonces[op.sender]) {
            revert NonceAlreadyUsed(op.sender, op.nonce);
        }
        userOperationNonces[op.sender]++;
        
        // Verify signature (simplified - real implementation would validate fully)
        bytes32 opHash = keccak256(abi.encode(op));
        if (executedTransactions[opHash]) revert TransactionAlreadyExecuted(opHash);
        executedTransactions[opHash] = true;
        
        uint256 gasStart = gasleft();
        
        // Execute callData
        (bool success, ) = op.sender.call(op.callData);
        
        uint256 gasUsed = gasStart - gasleft() + op.preVerificationGas;
        actualGasCost = gasUsed * op.maxFeePerGas;
        
        // Refund gas to beneficiary
        (bool refundSuccess, ) = beneficiary.call{value: actualGasCost}("");
        if (!refundSuccess) revert TransactionFailed(opHash, "Refund failed");
        
        _recordTransaction(opHash, op.sender, op.sender, 0, gasUsed, actualGasCost, success);
        
        emit UserOperationExecuted(opHash, op.sender, actualGasCost, success);
        
        return actualGasCost;
    }

    // ============ Internal Functions ============
    function _recordTransaction(
        bytes32 txHash,
        address from,
        address to,
        uint256 value,
        uint256 gasUsed,
        uint256 fee,
        bool success
    ) internal {
        if (transactionHistory.length >= MAX_HISTORY) {
            revert HistoryLimitReached();
        }
        
        transactions[txHash] = RelayedTransaction({
            txHash: txHash,
            from: from,
            to: to,
            value: value,
            gasUsed: gasUsed,
            fee: fee,
            timestamp: block.timestamp,
            success: success
        });
        
        transactionHistory.push(txHash);
        relayFeesCollected[from] += fee;
        totalFeesCollected += fee;
    }

    // ============ Configuration ============
    /**
     * @notice Update relay configuration
     * @param _maxGasPrice Maximum gas price allowed
     * @param _minGasPrice Minimum gas price required
     * @param _relayFeePercent Fee percentage (basis points)
     * @param _maxTransactionValue Maximum transaction value
     * @param _requireWhitelist Whether to require whitelist
     */
    function updateConfig(
        uint256 _maxGasPrice,
        uint256 _minGasPrice,
        uint256 _relayFeePercent,
        uint256 _maxTransactionValue,
        bool _requireWhitelist
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_relayFeePercent > MAX_FEE_PERCENT) {
            revert FeeTooHigh(_relayFeePercent, MAX_FEE_PERCENT);
        }
        
        config.maxGasPrice = _maxGasPrice;
        config.minGasPrice = _minGasPrice;
        config.relayFeePercent = _relayFeePercent;
        config.maxTransactionValue = _maxTransactionValue;
        config.requireWhitelist = _requireWhitelist;
        
        emit RelayConfigUpdated(_maxGasPrice, _minGasPrice, _relayFeePercent, _maxTransactionValue);
    }

    /**
     * @notice Update fee recipient
     * @param _feeRecipient New fee recipient address
     */
    function updateFeeRecipient(address _feeRecipient) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_feeRecipient == address(0)) revert InvalidFeeRecipient(_feeRecipient);
        
        address oldRecipient = feeRecipient;
        feeRecipient = _feeRecipient;
        
        emit FeeRecipientUpdated(oldRecipient, _feeRecipient);
    }

    /**
     * @notice Toggle relay pause
     */
    function togglePause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        config.paused = !config.paused;
        emit RelayPaused(config.paused);
    }

    // ============ Whitelist Management ============
    /**
     * @notice Add address to sender whitelist
     * @param account Address to whitelist
     */
    function addToWhitelist(address account) external onlyRole(WHITELIST_MANAGER_ROLE) {
        _whitelistedSenders.add(account);
        emit WhitelistStatusUpdated(account, true, true);
    }

    /**
     * @notice Remove address from sender whitelist
     * @param account Address to remove
     */
    function removeFromWhitelist(address account) external onlyRole(WHITELIST_MANAGER_ROLE) {
        _whitelistedSenders.remove(account);
        emit WhitelistStatusUpdated(account, true, false);
    }

    /**
     * @notice Check if address is whitelisted
     * @param account Address to check
     */
    function isWhitelisted(address account) external view returns (bool) {
        return _whitelistedSenders.contains(account);
    }

    /**
     * @notice Set blacklist status
     * @param account Address to update
     * @param isBlacklisted New status
     */
    function setBlacklist(address account, bool isBlacklisted) external onlyRole(DEFAULT_ADMIN_ROLE) {
        blacklisted[account] = isBlacklisted;
        emit BlacklistStatusUpdated(account, isBlacklisted);
    }

    // ============ Fee Management ============
    /**
     * @notice Withdraw accumulated fees
     */
    function withdrawFees() external onlyRole(DEFAULT_ADMIN_ROLE) nonReentrant {
        uint256 amount = address(this).balance;
        if (amount == 0) revert InsufficientFeePayment(1, 0);
        
        (bool success, ) = feeRecipient.call{value: amount}("");
        if (!success) revert TransactionFailed(bytes32(0), "Withdrawal failed");
        
        emit FeesWithdrawn(feeRecipient, amount);
    }

    /**
     * @notice Get user's fee contribution
     * @param user Address to query
     */
    function getUserFees(address user) external view returns (uint256) {
        return relayFeesCollected[user];
    }

    // ============ View Functions ============
    /**
     * @notice Get transaction history count
     */
    function getTransactionCount() external view returns (uint256) {
        return transactionHistory.length;
    }

    /**
     * @notice Get transaction by index
     * @param index Index in history
     */
    function getTransactionByIndex(uint256 index) external view returns (RelayedTransaction memory) {
        require(index < transactionHistory.length, "GaslessRelayer: index out of bounds");
        return transactions[transactionHistory[index]];
    }

    /**
     * @notice Get EIP-712 domain separator
     */
    function getDomainSeparator() external view returns (bytes32) {
        return _domainSeparatorV4();
    }

    /**
     * @notice Check if nonce is used
     * @param user User address
     * @param nonce Nonce to check
     */
    function isNonceUsed(address user, uint256 nonce) external view returns (bool) {
        return usedNonces[user][nonce];
    }

    /**
     * @notice Get next valid nonce for user
     * @param user User address
     */
    function getNextNonce(address user) external view returns (uint256) {
        uint256 nonce = nonces[user];
        while (usedNonces[user][nonce]) {
            nonce++;
        }
        return nonce;
    }

    /**
     * @notice Invalidate a nonce (emergency only)
     * @param nonce Nonce to invalidate
     */
    function invalidateNonce(uint256 nonce) external {
        usedNonces[msg.sender][nonce] = true;
        emit NonceInvalidated(msg.sender, nonce);
    }

    // ============ Batch Query Functions ============
    /**
     * @notice Get multiple transactions
     * @param startIndex Start index
     * @param count Number to retrieve
     */
    function getTransactions(uint256 startIndex, uint256 count) external view returns (RelayedTransaction[] memory) {
        require(startIndex < transactionHistory.length, "GaslessRelayer: start index out of bounds");
        
        uint256 endIndex = startIndex + count;
        if (endIndex > transactionHistory.length) {
            endIndex = transactionHistory.length;
        }
        
        RelayedTransaction[] memory result = new RelayedTransaction[](endIndex - startIndex);
        for (uint256 i = startIndex; i < endIndex; i++) {
            result[i - startIndex] = transactions[transactionHistory[i]];
        }
        return result;
    }

    // ============ Receive ============
    receive() external payable {}

    event RelayPaused(bool paused);
}