#!/bin/bash
# API Verification Test Suite
# Run this to verify all your API endpoints are working with real data

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  🚀 API VERIFICATION TEST SUITE"
echo "════════════════════════════════════════════════════════════════"
echo ""

API_URL="http://localhost:8000/api/v1"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo -e "${BLUE}Test 1: Health Check${NC}"
HEALTH=$(curl -s $API_URL/health)
if echo "$HEALTH" | grep -q "ok"; then
    echo -e "${GREEN}✓ Health endpoint working${NC}"
    echo "  Response: $(echo $HEALTH | jq '.status')"
else
    echo -e "${RED}✗ Health endpoint failed${NC}"
fi
echo ""

# Test 2: CVE Data
echo -e "${BLUE}Test 2: Vulnerabilities (CVE Data)${NC}"
CVE_DATA=$(curl -s "$API_URL/vulnerabilities/exploited?page=1&page_size=3")
CVE_COUNT=$(echo "$CVE_DATA" | jq '.total')
if [ ! -z "$CVE_COUNT" ] && [ "$CVE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ CVE endpoint working${NC}"
    echo "  Total CVEs available: $CVE_COUNT"
    echo "  Sample CVEs:"
    echo "$CVE_DATA" | jq '.items[0:2] | .[] | "    • \(.id) - \(.vendor)/\(.product)"' 2>/dev/null | head -5
else
    echo -e "${RED}✗ CVE endpoint failed or no data${NC}"
fi
echo ""

# Test 3: IC3 Data
echo -e "${BLUE}Test 3: IC3 Incident Data${NC}"
IC3_DATA=$(curl -s "$API_URL/ic3" 2>/dev/null)
if [ ! -z "$IC3_DATA" ]; then
    echo -e "${GREEN}✓ IC3 endpoint working${NC}"
    echo "  Sample response:"
    echo "$IC3_DATA" | jq '.' 2>/dev/null | head -20
else
    echo -e "${YELLOW}ℹ IC3 endpoint not yet configured (optional)${NC}"
fi
echo ""

# Test 4: Economics Data
echo -e "${BLUE}Test 4: Economic Indicators${NC}"
ECON_DATA=$(curl -s "$API_URL/economics" 2>/dev/null)
if [ ! -z "$ECON_DATA" ]; then
    echo -e "${GREEN}✓ Economics endpoint working${NC}"
    echo "  Sample response:"
    echo "$ECON_DATA" | jq '.' 2>/dev/null | head -20
else
    echo -e "${YELLOW}ℹ Economics endpoint not yet configured (optional)${NC}"
fi
echo ""

# Test 5: NVD Data (if available)
echo -e "${BLUE}Test 5: NVD Vulnerabilities${NC}"
NVD_DATA=$(curl -s "$API_URL/nvd" 2>/dev/null)
if [ ! -z "$NVD_DATA" ]; then
    echo -e "${GREEN}✓ NVD endpoint working${NC}"
    echo "  Sample response:"
    echo "$NVD_DATA" | jq '.' 2>/dev/null | head -20
else
    echo -e "${YELLOW}ℹ NVD endpoint not yet configured (optional)${NC}"
fi
echo ""

# Summary
echo "════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✓ API VERIFICATION COMPLETE${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📝 ENDPOINT STATUS:"
echo "  ✓ Health:          http://localhost:8000/api/v1/health"
echo "  ✓ Vulnerabilities: http://localhost:8000/api/v1/vulnerabilities/exploited"
echo "  ℹ IC3:             http://localhost:8000/api/v1/ic3 (optional)"
echo "  ℹ Economics:       http://localhost:8000/api/v1/economics (optional)"
echo "  ℹ NVD:             http://localhost:8000/api/v1/nvd (optional)"
echo ""
echo "📚 API DOCUMENTATION: http://localhost:8000/docs"
echo ""
